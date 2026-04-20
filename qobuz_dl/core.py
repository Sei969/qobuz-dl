import logging
import os
import sys
import time

import requests
from pathvalidate import sanitize_filename

from qobuz_dl.bundle import Bundle
from qobuz_dl import downloader, qopy
from qobuz_dl.color import CYAN, OFF, RED, YELLOW, DF, RESET
from qobuz_dl.exceptions import NonStreamable
from qobuz_dl.db import create_db, handle_download_id
from qobuz_dl.utils import (
    get_url_info,
    make_m3u,
    smart_discography_filter,
    format_duration,
    create_and_return_dir,
    PartialFormatter,
)
from qobuz_dl.settings import QobuzDLSettings

# --- UI TABLE FORMATTING HELPER ---
def _align_text(text, width):
    """Truncates text with '...' if too long, or pads with spaces if too short."""
    text = str(text)
    if len(text) > width:
        return text[:width - 3] + "..."
    return text.ljust(width)
# ----------------------------------

WEB_URL = "https://play.qobuz.com/"
ARTISTS_SELECTOR = "td.chartlist-artist > a"
TITLE_SELECTOR = "td.chartlist-name > a"
QUALITIES = {
    5: "5 - MP3",
    6: "6 - 16 bit, 44.1kHz",
    7: "7 - 24 bit, <96kHz",
    27: "27 - 24 bit, >96kHz",
}

logger = logging.getLogger(__name__)


class QobuzDL:
    def __init__(
        self,
        directory="QobuzDownloads",
        quality=6,
        embed_art=False,
        lucky_limit=1,
        lucky_type="album",
        interactive_limit=20,
        ignore_singles_eps=False,
        no_m3u_for_playlists=False,
        quality_fallback=True,
        cover_og_quality=False,
        no_cover=False,
        downloads_db=None,
        folder_format="{artist} - {album} ({year}) [{bit_depth}B-"
        "{sampling_rate}kHz]",
        track_format="{tracknumber}. {tracktitle}",
        smart_discography=False,
        fetch_lyrics=False,
        genius_token=None,
        force_english=True,
        no_credits=False,
        settings: QobuzDLSettings = None,
    ):
        self.directory = create_and_return_dir(directory)
        self.quality = quality
        self.embed_art = embed_art
        self.lucky_limit = lucky_limit
        self.lucky_type = lucky_type
        self.interactive_limit = interactive_limit
        self.ignore_singles_eps = ignore_singles_eps
        self.no_m3u_for_playlists = no_m3u_for_playlists
        self.quality_fallback = quality_fallback
        self.cover_og_quality = cover_og_quality
        self.no_cover = no_cover
        self.downloads_db = create_db(downloads_db) if downloads_db else None
        self.folder_format = folder_format
        self.track_format = track_format
        self.smart_discography = smart_discography
        self.fetch_lyrics = fetch_lyrics
        self.genius_token = genius_token
        self.force_english = force_english
        self.no_credits = no_credits
        self.settings = settings or QobuzDLSettings()

    def initialize_client(self, email, pwd, app_id, secrets):
        self.client = qopy.Client(email, pwd, app_id, secrets, self.settings.user_auth_token, force_english=self.force_english)
        logger.info(f"{YELLOW}Set max quality: {QUALITIES[int(self.quality)]}\n")

    def get_tokens(self):
        bundle = Bundle()
        self.app_id = bundle.get_app_id()
        self.secrets = [
            secret for secret in bundle.get_secrets().values() if secret
        ]  

    def download_from_id(self, item_id, album=True, alt_path=None, is_playlist=False, playlist_index=None):
        if handle_download_id(self.downloads_db, item_id, add_id=False, quality=self.quality):
            logger.info(
                f"{OFF}This release ID ({item_id}) was already downloaded "
                "according to the local database.\nUse the '--no-db' flag "
                "to bypass this."
            )
            return
        try:
            dloader = downloader.Download(
                self.client,
                item_id,
                alt_path or self.directory,
                int(self.quality),
                self.embed_art,
                self.ignore_singles_eps,
                self.quality_fallback,
                self.cover_og_quality,
                self.no_cover,
                self.folder_format,
                self.track_format,
                self.fetch_lyrics,
                self.genius_token,
                self.no_credits, 
                self.settings,
                self.downloads_db,
                is_playlist=is_playlist,
                playlist_track_number=playlist_index
            )
            dloader.download_id_by_type(not album)
        except (requests.exceptions.RequestException, NonStreamable) as e:
            logger.error(f"{RED}Error getting release: {e}. Skipping...")
            
        # --- HUMAN BEHAVIOR DELAY ---
        if getattr(self, 'delay', 0) > 0:
            logger.info(f"{YELLOW}[*] Sleeping for {self.delay} seconds to prevent rate limiting...{OFF}")
            time.sleep(self.delay)

    def handle_url(self, url):
        possibles = {
            "playlist": {
                "func": self.client.get_plist_meta,
                "iterable_key": "tracks",
            },
            "artist": {
                "func": self.client.get_artist_meta,
                "iterable_key": "albums",
            },
            "label": {
                "func": self.client.get_label_meta,
                "iterable_key": "albums",
            },
            "album": {"album": True, "func": None, "iterable_key": None},
            "track": {"album": False, "func": None, "iterable_key": None},
        }
        try:
            url_type, item_id = get_url_info(url)
            type_dict = possibles[url_type]
        except (KeyError, IndexError):
            logger.info(
                f'{RED}Invalid url: "{url}". Use urls from ' "https://play.qobuz.com!"
            )
            return
        if type_dict["func"]:
            content = [item for item in type_dict["func"](item_id)]
            content_name = content[0]["name"]
            logger.info(
                f"{YELLOW}Downloading all the music from {content_name} "
                f"({url_type})!"
            )
            new_path = create_and_return_dir(
                os.path.join(self.directory, sanitize_filename(content_name))
            )

            if self.smart_discography and url_type == "artist":
                items = smart_discography_filter(
                    content,
                    save_space=True,
                    skip_extras=True,
                )
            else:
                items = [item[type_dict["iterable_key"]]["items"] for item in content][
                    0
                ]

            logger.info(f"{YELLOW}{len(items)} downloads in queue")
            
            # --- START PLAYLIST LOGIC (Flat Folder) ---
            is_playlist = (url_type == "playlist")
            if is_playlist:
                original_folder_format = self.folder_format
                original_multi_disc_setting = self.settings.multiple_disc_one_dir
                
                self.folder_format = "."
                self.settings.multiple_disc_one_dir = True
            # ------------------------------------------------

            # Usiamo enumerate per avere il numero della traccia nella playlist (1, 2, 3...)
            for idx, item in enumerate(items, start=1):
                self.download_from_id(
                    item["id"],
                    True if type_dict["iterable_key"] == "albums" else False,
                    new_path,
                    is_playlist=is_playlist,
                    playlist_index=idx
                )

            # --- RESTORE SETTINGS ---
            if is_playlist:
                self.folder_format = original_folder_format
                self.settings.multiple_disc_one_dir = original_multi_disc_setting
            # -------------------------------

            if url_type == "playlist" and not self.no_m3u_for_playlists:
                make_m3u(new_path)
        else:
            self.download_from_id(item_id, type_dict["album"])

    def download_list_of_urls(self, urls):
        if not urls or not isinstance(urls, list):
            logger.info(f"{OFF}Nothing to download")
            return
        for url in urls:
            # --- FIX QOBUZ NEW DOMAIN LINKS ---
            url = url.replace("open.qobuz.com", "play.qobuz.com")
            
            if "last.fm" in url:
                self.download_lastfm_pl(url)
            elif os.path.isfile(url):
                self.download_from_txt_file(url)
            else:
                self.handle_url(url)

    def download_from_txt_file(self, txt_file):
        with open(txt_file, "r") as txt:
            try:
                urls = [
                    line.replace("\n", "")
                    for line in txt.readlines()
                    if not line.strip().startswith("#")
                ]
            except Exception as e:
                logger.error(f"{RED}Invalid text file: {e}")
                return
            logger.info(
                f"{YELLOW}qobuz-dl will download {len(urls)}"
                f" urls from file: {txt_file}"
            )
            self.download_list_of_urls(urls)

    def lucky_mode(self, query, download=True):
        if len(query) < 3:
            logger.info(f"{RED}Your search query is too short or invalid")
            return

        logger.info(
            f'{YELLOW}Searching {self.lucky_type}s for "{query}".\n'
            f"{YELLOW}qobuz-dl will attempt to download the first "
            f"{self.lucky_limit} results."
        )
        results = self.search_by_type(query, self.lucky_type, self.lucky_limit, True)

        if download:
            self.download_list_of_urls(results)

        return results

    def search_by_type(self, query, item_type, limit=10, lucky=False):
        if len(query) < 3:
            logger.info(f"{RED}Your search query is too short or invalid")
            return

        possibles = {
            "album": {
                "func": self.client.search_albums,
                "album": True,
                "key": "albums",
                "requires_extra": True,
            },
            "artist": {
                "func": self.client.search_artists,
                "album": True,
                "key": "artists",
                "requires_extra": False,
            },
            "track": {
                "func": self.client.search_tracks,
                "album": False,
                "key": "tracks",
                "requires_extra": True,
            },
            "playlist": {
                "func": self.client.search_playlists,
                "album": False,
                "key": "playlists",
                "requires_extra": False,
            },
        }

        try:
            mode_dict = possibles[item_type]
            results = mode_dict["func"](query, limit)
            iterable = results[mode_dict["key"]]["items"]
            item_list = []
            
            for i in iterable:
                if mode_dict["requires_extra"]:
                    artist = i.get("artist", {}).get("name") or i.get("performer", {}).get("name") or "Unknown"
                    
                    title = i.get("title") or i.get("name") or "Unknown"
                    if i.get("version"):
                        title = f"{title} ({i.get('version')})"
                    if i.get("parental_warning"):
                        title = f"{title} [E]"
                    
                    year = str(i.get("release_date_original") or i.get("release_date") or "    ")[:4]
                    
                    raw_type = i.get("release_type") or i.get("product_type")
                    if not raw_type:
                        t_count = i.get("tracks_count", 0)
                        duration = i.get("duration", 0) 
                        
                        if item_type == "album" and (t_count or duration):
                            if duration >= 1740 or t_count >= 7:
                                raw_type = "Album"
                            elif t_count == 1:
                                raw_type = "Single"
                            else:
                                raw_type = "EP"
                        else:
                            raw_type = item_type
                            
                    rel_type = "EP" if raw_type.lower() == "ep" else raw_type.title()
                    
                    if i.get("hires_streamable"):
                        bit_depth = i.get("maximum_bit_depth", 24)
                        sampling_rate = i.get("maximum_sampling_rate", 96.0)
                        quality = f"[HI-RES] {bit_depth}b/{sampling_rate}kHz"
                    else:
                        quality = "[ CD ] 16b/44.1kHz"
                        
                    # --- MODIFICA 1 APPLICATA QUI SOTTO: Via le '│', usiamo 3 spazi ---
                    text = f"{_align_text(artist, 20)}   {_align_text(title, 35)}   {_align_text(rel_type, 8)}   {year}   {quality}"
                else:
                    name = i.get("name", "Unknown")
                    count = i.get("albums_count") if "albums_count" in i else i.get("tracks_count", 0)
                    desc = "albums" if "albums_count" in i else "tracks"
                    
                    # --- MODIFICA 1 APPLICATA QUI SOTTO: Via le '│', usiamo 3 spazi ---
                    text = f"{_align_text(name, 50)}   {count} {desc}"

                url = "{}{}/{}".format(WEB_URL, item_type, i.get("id", ""))
                item_list.append({"text": text, "url": url} if not lucky else url)
            return item_list
            
        except (KeyError, IndexError):
            logger.info(f"{RED}Invalid type: {item_type}")
            return

    def interactive(self, download=True):
        try:
            import pick
            # --- WINDOWS TERMINAL FIX & MULTISELECT LOOK ---
            # Using clean, aligned square brackets for the multi-select interface
            if hasattr(pick, 'SYMBOL_CIRCLE_EMPTY'):
                pick.SYMBOL_CIRCLE_EMPTY = '[ ]'
                pick.SYMBOL_CIRCLE_FILLED = '[X]'
            # -----------------------------------------------
        except (ImportError, ModuleNotFoundError):
            if os.name == "nt":
                sys.exit(
                    "Please install curses with "
                    '"pip3 install windows-curses" to continue'
                )
            raise

        qualities = [
            {"q_string": "320", "q": 5},
            {"q_string": "Lossless", "q": 6},
            {"q_string": "Hi-res =< 96kHz", "q": 7},
            {"q_string": "Hi-Res > 96 kHz", "q": 27},
        ]

        try:
            item_types = ["Albums", "Tracks", "Artists", "Playlists"]
            selected_type = pick.pick(item_types, "I'll search for:\n[press Intro]")[0][:-1].lower()
            logger.info(f"{YELLOW}Ok, we'll search for {selected_type}s{RESET}")
            final_url_list = []
            
            while True:
                query = input(f"{CYAN}Enter your search: [Ctrl + c to quit]\n-{DF} ")
                logger.info(f"{YELLOW}Searching...{RESET}")
                options = self.search_by_type(query, selected_type, self.interactive_limit)
                
                if not options:
                    logger.info(f"{OFF}Nothing found{RESET}")
                    continue
                
                # --- CALIBRATED MINIMAL HEADER (7 SPACES FOR PERFECT ALIGNMENT) ---
                if selected_type in ["album", "track"]:
                    artist_h = "ARTIST".ljust(20)
                    title_h = "TITLE".ljust(35)
                    type_h = "TYPE".ljust(8)
                    year_h = "YEAR".ljust(4)
                    
                    # Using 7 leading spaces to align the 'A' of ARTIST exactly above the first letter of the data
                    table_header = (
                        f"       {artist_h}   {title_h}   {type_h}   {year_h}   QUALITY\n"
                        f"       {'-' * 88}"
                    )
                else:
                    name_h = "NAME".ljust(50)
                    table_header = (
                        f"       {name_h}   RELEASES\n"
                        f"       {'-' * 63}"
                    )
                # ------------------------------------------------------------------

                title = (
                    f'*** RESULTS FOR "{query.title()}" ***\n\n'
                    "[Use arrows to move, <Space> to select, <Enter> to confirm]\n"
                    "Press Ctrl + C to quit. Don't select anything to try another search.\n\n"
                    f"{table_header}"
                )
                
                options_texts = [opt.get("text") for opt in options]
                
                selected_items = pick.pick(
                    options_texts,
                    title,
                    multiselect=True,
                    min_selection_count=0,
                )
                
                if len(selected_items) > 0:
                    [final_url_list.append(options[i[1]]["url"]) for i in selected_items]
                    
                    y_n = pick.pick(["Yes", "No"], "Items were added to queue to be downloaded. Keep searching?")
                    if y_n[0] == "No":
                        break
                else:
                    logger.info(f"{YELLOW}Ok, try again...{RESET}")
                    continue
                    
            if final_url_list:
                desc = "Select [intro] the quality (the quality will be automatically\ndowngraded if the selected is not found)"
                qualities_texts = [q.get("q_string") for q in qualities]
                selected_quality = pick.pick(qualities_texts, desc, default_index=1)
                self.quality = qualities[selected_quality[1]]["q"]

                if download:
                    self.download_list_of_urls(final_url_list)

                return final_url_list
                
        except KeyboardInterrupt:
            logger.info(f"{YELLOW}Bye")
            return

    def download_lastfm_pl(self, playlist_url):
        from qobuz_dl.lastfm_parser import fetch_lastfm_playlist
        
        logger.info(f"{CYAN}[*] Last.fm URL detected! Initiating Last.fm integration...{OFF}")
        
        # Step 1: Extract textual list from Last.fm using our isolated parser
        tracks_list = fetch_lastfm_playlist(playlist_url)
        
        if not tracks_list:
            logger.info(f"{YELLOW}[!] Last.fm processing aborted (no tracks).{OFF}")
            return

        # Extract an ID from the Last.fm URL to name the folder
        pl_id = playlist_url.rstrip('/').split('/')[-1]
        pl_title = sanitize_filename(f"LastFM_Playlist_{pl_id}")
        pl_directory = os.path.join(self.directory, pl_title)
        
        logger.info(
            f"{YELLOW}Downloading playlist: {pl_title} ({len(tracks_list)} tracks){RESET}"
        )

        # Step 2: Convert to Qobuz IDs using our new method in qopy.py
        track_ids = self.client.get_track_ids_from_list(tracks_list)
        
        if not track_ids:
            logger.info(f"{RED}[!] No matching tracks found on Qobuz. Aborting.{OFF}")
            return

        # Step 3: Send valid IDs to the downloader engine
        
        # Save original settings to restore them later
        original_folder_format = self.folder_format
        original_multi_disc_setting = self.settings.multiple_disc_one_dir
        
        # Force flat folder structure for the playlist
        self.folder_format = "."
        self.settings.multiple_disc_one_dir = True
        
        # Use enumerate to get the playlist track number (1, 2, 3...)
        for idx, t_id in enumerate(track_ids, start=1):
            try:
                self.download_from_id(
                    t_id, 
                    False, 
                    pl_directory, 
                    is_playlist=True, 
                    playlist_index=idx
                )
            except Exception as e:
                logger.error(f"{RED}[!] Failed to queue track ID {t_id}: {e}{OFF}")

        # Restore original settings for subsequent downloads
        self.folder_format = original_folder_format
        self.settings.multiple_disc_one_dir = original_multi_disc_setting

        if not self.no_m3u_for_playlists:
            make_m3u(pl_directory)