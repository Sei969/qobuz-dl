import logging
import os
import sys
import re

import requests
import questionary
from prompt_toolkit.styles import Style
from pathvalidate import sanitize_filename

from qobuz_dl.bundle import Bundle
from qobuz_dl import downloader, qopy
from qobuz_dl.color import CYAN, OFF, RED, YELLOW, DF, RESET, GREEN
from qobuz_dl.exceptions import NonStreamable
from qobuz_dl.db import create_db, handle_download_id
from qobuz_dl.utils import (
    get_url_info,
    make_m3u,
    smart_discography_filter,
    label_matches,
    format_duration,
    create_and_return_dir,
    PartialFormatter,
)
from qobuz_dl.settings import QobuzDLSettings

# --- UI STYLING FOR QUESTIONARY ---
Q_STYLE = Style([
    ("qmark", "fg:#00ffff bold"),
    ("question", "bold"),
    ("answer", "fg:#f44336 bold"),
    ("pointer", "fg:#00ffff bold"),
    ("highlighted", "fg:#00ffff bold"),
    ("selected", "fg:#cc5454"),
    ("separator", "fg:#cc5454"),
    ("instruction", ""),
    ("text", ""),
])
# ----------------------------------

import unicodedata

# --- UI TABLE FORMATTING HELPER ---
def _align_text(text, width):
    """
    Truncates text with '...' if its terminal display width exceeds the specified width, 
    or pads it with spaces to ensure perfect UI table alignment (including CJK characters).

    Args:
        text (str): The text to format.
        width (int): The maximum terminal column width.

    Returns:
        str: The aligned and formatted string.
    """
    text = str(text)

    def _char_width(ch):
        return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1

    disp_len = sum(_char_width(c) for c in text)
    if disp_len > width:
        out = []
        cur = 0
        for c in text:
            w = _char_width(c)
            if cur + w > width - 3:
                break
            out.append(c)
            cur += w
        return "".join(out) + "..." + " " * (width - cur - 3)
    return text + " " * (width - disp_len)
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
    """
    The main orchestrator class for Qobuz-DL Ultimate Edition.
    
    Ties together the API Client, Downloader, UI routing, and advanced automations 
    such as Stateful Batch Downloading, Anti-Spam Blacklisting, and Interactive UI menus.
    """

    def __init__(
        self,
        directory="QobuzDownloads",
        quality=6,
        embed_art=False,
        lucky_limit=1,
        lucky_type="album",
        interactive_limit=20,
        interactive_sort_date=False,
        ignore_singles_eps=False,
        no_m3u_for_playlists=False,
        quality_fallback=True,
        cover_og_quality=False,
        no_cover=False,
        downloads_db=None,
        folder_format="{artist} - {album} ({year}) [{bit_depth}B-"
        "{sampling_rate}kHz]",
        track_format="{track_number} - {track_title}",
        smart_discography=False,
        fetch_lyrics=False,
        no_lrc_files=False,
        synced_lyrics_only=False,
        genius_token=None,
        force_english=True,
        no_credits=False,
        settings: QobuzDLSettings = None,
        booklet_only: bool = False,
        blacklist=None,
        playlist_as_albums: bool = False,
        album_tag_format: str = "",
        date_tag_format: str = "",
        genre_tag_format: str = "",
    ):
        """
        Initializes the Core application and parses settings.

        Args:
            directory (str): Base output directory. Defaults to "QobuzDownloads".
            quality (int): Target audio format ID. Defaults to 6.
            embed_art (bool): Enables embedded album art. Defaults to False.
            lucky_limit (int): Number of items to fetch in lucky mode. Defaults to 1.
            lucky_type (str): The entity type for lucky mode searches. Defaults to "album".
            interactive_limit (int): Max results displayed in the CLI menu. Defaults to 20.
            ignore_singles_eps (bool): Skips non-album releases. Defaults to False.
            no_m3u_for_playlists (bool): Disables .m3u playlist generation. Defaults to False.
            quality_fallback (bool): Automatically downgrades quality if target is unavailable. Defaults to True.
            cover_og_quality (bool): Fetches original uncompressed cover art. Defaults to False.
            no_cover (bool): Completely skips cover art downloading. Defaults to False.
            downloads_db (str): Path to the SQLite DB for Smart Reverse Lookup. Defaults to None.
            folder_format (str): Directory naming template.
            track_format (str): File naming template.
            smart_discography (bool): Enables Smart Discography filtering. Defaults to False.
            fetch_lyrics (bool): Enables Roon-Ready Synchronized Lyrics. Defaults to False.
            no_lrc_files (bool): Disables external .lrc generation. Defaults to False.
            genius_token (str): API Token for Genius fallback lyrics. Defaults to None.
            force_english (bool): Enforces en_US locales to bypass WAF bans. Defaults to True.
            no_credits (bool): Disables Digital Booklet generation. Defaults to False.
            settings (QobuzDLSettings): Configuration object mapping config.ini variables.
            booklet_only (bool): Downloads only metadata and artwork, skipping audio. Defaults to False.
            blacklist (str): Path to the .txt file for the Anti-Spam Blacklist Engine. Defaults to None.
            playlist_as_albums (bool): Downloads playlist tracks into their respective album folders. Defaults to False.
        """
        self.directory = create_and_return_dir(directory)
        self.quality = quality
        self.embed_art = embed_art
        self.lucky_limit = lucky_limit
        self.lucky_type = lucky_type
        self.interactive_limit = interactive_limit
        self.interactive_sort_date = interactive_sort_date
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
        self.no_lrc_files = no_lrc_files
        self.synced_lyrics_only = synced_lyrics_only
        self.genius_token = genius_token
        self.force_english = force_english
        self.no_credits = no_credits
        self.settings = settings or QobuzDLSettings()
        self.booklet_only = booklet_only
        self.playlist_as_albums = playlist_as_albums
        self.album_tag_format = album_tag_format
        self.date_tag_format = date_tag_format
        self.genre_tag_format = genre_tag_format
        
        self.blacklist_patterns = []
        if blacklist and os.path.isfile(blacklist):
            try:
                with open(blacklist, "r", encoding="utf-8") as f:
                    self.blacklist_patterns = [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]
                logger.info(f"{YELLOW}[*] Blacklist loaded: {len(self.blacklist_patterns)} patterns active.{OFF}")
            except Exception as e:
                logger.error(f"{RED}[!] Failed to load blacklist: {e}{OFF}")
        
    def initialize_client(self, email, pwd, app_id, secrets):
        """Authenticates the session and initializes the Stealth Spoofing client."""
        self.client = qopy.Client(email, pwd, app_id, secrets, self.settings.user_auth_token, force_english=self.force_english)
        logger.info(f"{YELLOW}Set max quality: {QUALITIES[int(self.quality)]}\n")

    def get_tokens(self):
        """Fetches dynamic Application IDs and Secrets from the internal bundle."""
        bundle = Bundle()
        self.app_id = bundle.get_app_id()
        self.secrets = [
            secret for secret in bundle.get_secrets().values() if secret
        ]  

    def download_from_id(self, item_id, album=True, alt_path=None, is_playlist=False, playlist_index=None, ignore_db=False):
        """
        Routes the item ID to the Downloader Engine, checking the SQLite database
        first to prevent duplicates (Smart Reverse Lookup).
        With ignore_db=True the item is downloaded even if the database lists it
        (used by sync-playlist for tracks it found missing in the folder).
        """
        if not ignore_db and handle_download_id(self.downloads_db, item_id, add_id=False, quality=self.quality):
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
                self.no_lrc_files,
                self.synced_lyrics_only,
                self.genius_token,
                self.no_credits, 
                self.settings,
                self.downloads_db,
                is_playlist=is_playlist,
                playlist_track_number=playlist_index,
                booklet_only=self.booklet_only,
                playlist_as_albums=self.playlist_as_albums,
                album_tag_format=self.album_tag_format,
                date_tag_format=self.date_tag_format,
                genre_tag_format=self.genre_tag_format,
            )
            dloader.download_id_by_type(not album)
        except (requests.exceptions.RequestException, NonStreamable) as e:
            logger.error(f"{RED}Error getting release: {e}. Skipping...")

        # No --delay pause here: the downloader already sleeps after every track,
        # including the last one of an album, so a second pause would double it.

    def handle_url(self, url):
        """
        Parses raw Qobuz URLs, resolving their type (Playlist, Artist, Album, Track) 
        and forwarding the respective IDs to the download engine. 
        Implements the Heuristic Engine for artist discographies and Flat Folder logic for playlists.
        """
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
        except (KeyError, IndexError, AttributeError):
            # AttributeError: get_url_info() found no known URL pattern
            logger.info(
                f'{RED}Invalid url: "{url}". Use urls from ' "https://play.qobuz.com!"
            )
            return
        if type_dict["func"]:
            content = [item for item in type_dict["func"](item_id)]
            
            if not content:
                logger.warning(
                    f"{YELLOW}[!] Skipped URL: Content empty or unavailable (Geo-blocked/Removed). URL: {url}{OFF}"
                )
                return
            content_name = content[0]["name"]
            logger.info(
                f"{YELLOW}Downloading all the music from {content_name} "
                f"({url_type})!"
            )
            new_path = create_and_return_dir(
                os.path.join(self.directory, sanitize_filename(content_name))
            )

            # --- LABEL INTERSECTION PRE-FILTER ---
            # The artist listing already carries each release's label, so releases from
            # other labels are dropped here instead of fetching their full metadata first.
            # It runs before the smart discography filter, so that one picks the best
            # version among the releases on the requested label.
            # Items without label data are kept and checked again during the download.
            filter_label = getattr(self.settings, "filter_label", None)
            if filter_label and url_type == "artist":
                total = matching = 0
                for chunk in content:
                    albums = chunk.get(type_dict["iterable_key"]) or {}
                    batch = albums.get("items", [])
                    albums["items"] = [
                        item for item in batch
                        if "label" not in item or label_matches(item.get("label"), filter_label)
                    ]
                    total += len(batch)
                    matching += len(albums["items"])
                logger.info(
                    f"{YELLOW}[*] Label filter: {matching} of {total} releases "
                    f"match \"{filter_label}\"{OFF}"
                )
            # --------------------------------------

            if self.smart_discography and url_type == "artist":
                items = smart_discography_filter(
                    content,
                    save_space=True,
                    skip_extras=True,
                )
            else:
                items = []
                for chunk in content:
                    batch = chunk.get(type_dict["iterable_key"], {}).get("items", [])
                    items.extend(batch)

            # --- NEW: INTERACTIVE RELEASE TYPE FILTER (LAZY STATIC MENU) ---
            if getattr(self, '_is_interactive_session', False) and url_type == "artist":
                # 1. Static options for exact Lazy Evaluation
                options = ["Album", "EP", "Single", "Live", "Compilation"]
                
                title_text = (
                    f"Found {len(items)} total releases for {content_name}.\n"
                    "Filter by release type [Use arrows to move, Space to select, Enter to confirm]:\n"
                    "(The exact count per category will be resolved silently during download)"
                )
                
                # Trigger the multiselect UI via Questionary
                selected_types_raw = questionary.checkbox(
                    title_text,
                    choices=options,
                    style=Q_STYLE,
                ).ask()
                
                if selected_types_raw:
                    self.allowed_release_types = [opt.lower() for opt in selected_types_raw]
                else:
                    # User cancelled or selected nothing
                    self.allowed_release_types = []
                    items = []
            else:
                self.allowed_release_types = None
            # ---------------------------------------------------------------

            logger.debug(f"Number of chunks: {len(content)}")
            if content:
                logger.debug(f"Items in first chunk: {len(content[0].get(type_dict['iterable_key'], {}).get('items', []))}")
            if getattr(self, 'allowed_release_types', None) is not None:
                logger.info(f"{YELLOW}[*] Evaluating {len(items)} releases (unwanted types will be skipped silently)...{OFF}")
            else:
                logger.info(f"{YELLOW}{len(items)} downloads in queue{OFF}")
            
            # --- START PLAYLIST LOGIC (Flat Folder) ---
            is_playlist = (url_type == "playlist")
            if is_playlist and not getattr(self, 'playlist_as_albums', False):
                original_folder_format = self.folder_format
                original_multi_disc_setting = self.settings.multiple_disc_one_dir
                
                self.folder_format = "."
                self.settings.multiple_disc_one_dir = True
            # ------------------------------------------------

            # --- FASE 1: Smart Reconciler & Blacklist ---
            valid_items = []
            for item in items:
                # 1. Ultimate Smart Reconciler
                if getattr(self, 'allowed_release_types', None) and url_type == "artist":
                    try:
                        r_type = "unknown"
                        full_meta = None
                        if hasattr(self.client, "get_album_meta"):
                            full_meta = self.client.get_album_meta(item["id"])
                        elif hasattr(self.client, "get_album"):
                            full_meta = self.client.get_album(item["id"])
                            
                        if full_meta:
                            r_type = (full_meta.get("release_type") or full_meta.get("product_type") or "unknown").lower()
                            
                        base_title = str(item.get("title", "")).lower()
                        version_tag = str(item.get("version", "")).lower()
                        t_count = item.get("tracks_count", 0)
                        
                        if "live" in version_tag or "(live" in base_title or "- live" in base_title:
                            r_type = "live"
                        elif any(kw in base_title or kw in version_tag for kw in ["best of", "greatest hits", "anthology", "collection", "compilation"]):
                            r_type = "compilation"
                        elif " ep" in base_title or version_tag == "ep":
                            r_type = "ep"
                        elif r_type == "single" and t_count >= 4:
                            r_type = "ep"
                        elif r_type in ["ep", "album"] and 1 <= t_count <= 3:
                            r_type = "single"
                        elif r_type == "unknown":
                            if 1 <= t_count <= 3: r_type = "single"
                            elif 4 <= t_count <= 6: r_type = "ep"
                            else: r_type = "album"

                        if r_type not in self.allowed_release_types:
                            continue
                    except Exception:
                        pass
                
                # 2. Anti-Spam Blacklist Engine
                if getattr(self, 'blacklist_patterns', None):
                    base_title = item.get("title") or item.get("name") or ""
                    version_tag = item.get("version") or ""
                    display_name = f"{base_title} ({version_tag})" if version_tag else base_title
                    display_lower = display_name.lower()
                    
                    is_blacklisted = any(re.search(rf"(?<!\w){re.escape(pattern)}(?!\w)", display_lower) for pattern in self.blacklist_patterns)
                    if is_blacklisted:
                        logger.info(f"{YELLOW}[!] Skipped (Blacklisted): {display_name}{OFF}")
                        continue
                        
                valid_items.append(item)

            # --- FASE 2: INTERACTIVE MENU ---
            if getattr(self, '_is_interactive_session', False) and url_type == "artist" and valid_items:
                import time
                
                choices = [
                    questionary.Choice(
                        title="==> [ DOWNLOAD ALL FILTERED RELEASES ] <==",
                        value=0,
                    )
                ]
                for idx, v_item in enumerate(valid_items, start=1):
                    t_title = v_item.get("title") or v_item.get("name") or "Unknown"
                    t_ver = v_item.get("version")
                    t_disp = f"{t_title} ({t_ver})" if t_ver else t_title
                    t_year = str(v_item.get("release_date_original") or v_item.get("release_date") or "")[:4]
                    label = f"{t_disp} [{t_year}]" if t_year else t_disp
                    choices.append(questionary.Choice(title=label, value=idx))
                    
                title_text = (
                    f"Found {len(valid_items)} filtered releases for {content_name}.\n"
                    "Select specific albums to download [Space to select, Enter to confirm]:"
                )
                
                time.sleep(0.4)
                
                selected_indices = questionary.checkbox(
                    title_text,
                    choices=choices,
                    style=Q_STYLE,
                ).ask()
                
                if not selected_indices:
                    valid_items = []
                    logger.info(f"{YELLOW}[*] No releases selected. Skipping...{OFF}")
                elif 0 not in selected_indices:
                    valid_items = [valid_items[i - 1] for i in selected_indices]
                    logger.info(f"{YELLOW}[*] Proceeding with {len(valid_items)} manually selected releases.{OFF}")
                else:
                    logger.info(f"{YELLOW}[*] Proceeding with ALL {len(valid_items)} releases.{OFF}")

            # --- FASE 3: DOWNLOAD QUEUE ---
            queued_items = []
            for idx, item in enumerate(valid_items, start=1):
                queued_items.append(item)
                self.download_from_id(
                    item["id"],
                    True if type_dict["iterable_key"] == "albums" else False,
                    new_path,
                    is_playlist=is_playlist,
                    playlist_index=idx
                )

                # NOTA ARCHITETTURALE: Le righe seguenti (presenti nel vecchio core.py)
                # eseguivano una seconda volta il filtro già completato in Fase 1 e
                # invocavano una seconda volta download_from_id sullo stesso brano.
                # --- NEW: ULTIMATE SMART RECONCILER (LAZY + HEURISTIC) ---
                # if getattr(self, 'allowed_release_types', None) and url_type == "artist":
                #     try:
                #         r_type = "unknown"
                #         full_meta = None
                #         if hasattr(self.client, "get_album_meta"):
                #             full_meta = self.client.get_album_meta(item["id"])
                #         elif hasattr(self.client, "get_album"):
                #             full_meta = self.client.get_album(item["id"])
                #         if full_meta:
                #             r_type = (full_meta.get("release_type") or full_meta.get("product_type") or "unknown").lower()
                #         base_title = str(item.get("title", "")).lower()
                #         version_tag = str(item.get("version", "")).lower()
                #         t_count = item.get("tracks_count", 0)
                #         if "live" in version_tag or "(live" in base_title or "- live" in base_title:
                #             r_type = "live"
                #         elif any(kw in base_title or kw in version_tag for kw in ["best of", "greatest hits", "anthology", "collection", "compilation"]):
                #             r_type = "compilation"
                #         elif " ep" in base_title or version_tag == "ep":
                #             r_type = "ep"
                #         elif r_type == "single" and t_count >= 4:
                #             r_type = "ep"
                #         elif r_type == "ep" and 1 <= t_count <= 3:
                #             r_type = "single"
                #         elif r_type == "album" and 1 <= t_count <= 3:
                #             r_type = "single"
                #         elif r_type == "unknown":
                #             if 1 <= t_count <= 3:
                #                 r_type = "single"
                #             elif 4 <= t_count <= 6:
                #                 r_type = "ep"
                #             else:
                #                 r_type = "album"
                #         if r_type not in self.allowed_release_types:
                #             continue
                #     except Exception:
                #         pass
                # ---------------------------------------------------------

            # --- RESTORE SETTINGS ---
            if is_playlist and not getattr(self, 'playlist_as_albums', False):
                self.folder_format = original_folder_format
                self.settings.multiple_disc_one_dir = original_multi_disc_setting
            # -------------------------------

            if url_type == "playlist" and not self.no_m3u_for_playlists:
                # The playlist files carry no position in their names, so the .m3u is
                # ordered by matching them to the playlist tracks (as sync-playlist does)
                make_m3u(new_path, queued_items)
        else:
            self.download_from_id(item_id, type_dict["album"])

    # --- SMART RESUME / BATCH DOWNLOADER LOGIC ---
    def mark_url_done_in_file(self, txt_file, url_to_mark):
        """
        Appends a [DONE] tag next to a processed URL in a text file.
        Enables the Stateful Batch Downloading feature.

        Args:
            txt_file (str): Path to the text file containing URLs.
            url_to_mark (str): The specific URL string to mark as completed.
        """
        if not txt_file or not os.path.isfile(txt_file):
            return
        try:
            with open(txt_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            with open(txt_file, "w", encoding="utf-8") as f:
                for line in lines:
                    # Safely compare by stripping whitespaces to avoid mismatch bugs
                    if line.strip() == url_to_mark.strip():
                        f.write(f"{line.rstrip()} [DONE]\n")
                    else:
                        f.write(line)
        except Exception as e:
            logger.error(f"{RED}Failed to update text file status: {e}{OFF}")

    def download_list_of_urls(self, urls, txt_file=None):
        """Processes a raw list of URLs, routing Qobuz and Last.fm links accordingly."""
        if not urls or not isinstance(urls, list):
            logger.info(f"{OFF}Nothing to download")
            return
        for url in urls:
            # --- FIX QOBUZ NEW DOMAIN LINKS ---
            original_url = url
            url = url.replace("open.qobuz.com", "play.qobuz.com")
            
            if "last.fm" in url:
                self.download_lastfm_pl(url)
                self.mark_url_done_in_file(txt_file, original_url)
            elif os.path.isfile(url):
                self.download_from_txt_file(url)
            else:
                self.handle_url(url)
                self.mark_url_done_in_file(txt_file, original_url)

    def download_from_txt_file(self, txt_file):
        """
        Ingests a text file containing Qobuz URLs, filtering out completed items, 
        comments, and invalid lines, before pushing them to the batch engine.
        """
        try:
            valid_urls = []
            with open(txt_file, "r", encoding="utf-8") as txt:
                # Optimized memory usage: read line by line instead of readlines()
                for line in txt:
                    line = line.strip()
                    # Skip empty lines, comments, or already processed links
                    if not line or line.startswith("#") or "[DONE]" in line:
                        continue
                    
                    # Validate if it's a Qobuz or Last.fm URL
                    if "last.fm" in line:
                        valid_urls.append(line)
                    else:
                        try:
                            get_url_info(line)
                            valid_urls.append(line)
                        except (KeyError, IndexError, AttributeError):
                            logger.debug(f"Skipping invalid URL line: {line}")
                        
        except Exception as e:
            logger.error(f"{RED}Invalid text file: {e}{OFF}")
            return
            
        if not valid_urls:
            logger.info(f"{OFF}No new valid URLs found in file: {txt_file}")
            return
            
        logger.info(
            f"{YELLOW}qobuz-dl will download {len(valid_urls)}"
            f" urls from file: {txt_file}{OFF}"
        )
        self.download_list_of_urls(valid_urls, txt_file=txt_file)
    # ---------------------------------------------

    def lucky_mode(self, query, download=True):
        """Automatically fetches and downloads the top result for a given query."""
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

    def search_by_type(self, query, item_type, limit=10, lucky=False, fav_subtype=None):
        """
        Routes text queries to the Qobuz API. Supports native search for Albums, 
        Artists, Tracks, Playlists, and the authenticated user's private Favorites.

        Args:
            query (str): The search keyword.
            item_type (str): Category (e.g., 'album', 'favorites').
            limit (int): Max results to retrieve.
            lucky (bool): If True, returns only URLs. If False, returns formatted dicts.
            fav_subtype (str, optional): Required if item_type is 'favorites'.
        """
        # Prevent crash if query is None (which happens when searching favorites)
        if item_type != "favorites" and (not query or len(query) < 3):
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
            "favorites": {
                "func": self.client.get_favorites,
                "album": True, # Depends on the subtype, defaults to True for pagination
                "key": "favorites", # Placeholder, handled below
                "requires_extra": True,
            }
        }

        try:
            mode_dict = possibles[item_type]
            
            # --- NEW FAVORITES EXTRACTION LOGIC ---
            if item_type == "favorites":
                # API call for favorites
                results = mode_dict["func"](fav_type=fav_subtype, limit=limit)
                iterable = results.get(fav_subtype, {}).get("items", [])
                
                # Adjust requires_extra based on the subtype for the minimalist table
                if fav_subtype in ["artists", "playlists"]:
                    mode_dict["requires_extra"] = False
                else:
                    mode_dict["requires_extra"] = True
            else:
                # Standard API call
                results = mode_dict["func"](query, limit)
                iterable = results[mode_dict["key"]]["items"]
            # --------------------------------------------
            # INTERACTIVE SORT BY DATE ---
            # Sorts the parsed API iterable by release date (descending) before rendering the UI
            if getattr(self, 'interactive_sort_date', False) and item_type in ["album", "track"]:
                try:
                    iterable = sorted(
                        iterable,
                        key=lambda x: str(x.get("release_date_original") or x.get("release_date") or "0000"),
                        reverse=True
                    )
                except Exception as e:
                    logger.debug(f"Sorting by date failed: {e}")
            # -------------------------------------
            
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
                        
                    # --- FIX 1 APPLIED BELOW: Removed '│' separators, using 3 spaces ---
                    text = f"{_align_text(artist, 20)}   {_align_text(title, 35)}   {_align_text(rel_type, 8)}   {year}   {quality}"
                else:
                    name = i.get("name", "Unknown")
                    count = i.get("albums_count") if "albums_count" in i else i.get("tracks_count", 0)
                    desc = "albums" if "albums_count" in i else "tracks"
                    
                    # --- FIX 1 APPLIED BELOW: Removed '│' separators, using 3 spaces ---
                    text = f"{_align_text(name, 50)}   {count} {desc}"

                # --- FAVORITES FIX URL ---
                if item_type == "favorites" and fav_subtype:
                    # Remove the trailing 's' (albums -> album, tracks -> track)
                    url_category = fav_subtype[:-1]
                else:
                    url_category = item_type
                    
                url = "{}{}/{}".format(WEB_URL, url_category, i.get("id", ""))
                item_list.append({"text": text, "url": url} if not lucky else url)
            return item_list
            
        except (KeyError, IndexError):
            logger.info(f"{RED}Invalid type: {item_type}")
            return

    def interactive(self, download=True):
        """
        Launches the Native Interactive Menu in the terminal.
        
        Features a graphical multi-select interface (via the 'questionary' library) to browse 
        the Qobuz catalog or the user's private Favorites, queueing up batches of URLs 
        for downloading.
        """
        # --- NEW: Flag to let the engine know we are in a TTY session ---
        self._is_interactive_session = True
        # ----------------------------------------------------------------

        qualities = [
            {"q_string": "320", "q": 5},
            {"q_string": "Lossless", "q": 6},
            {"q_string": "Hi-res =< 96kHz", "q": 7},
            {"q_string": "Hi-Res > 96 kHz", "q": 27},
        ]

        try:
            item_types = ["Albums", "Tracks", "Artists", "Playlists", "Favorites"]
            
            # Get the exact choice
            scelta_raw = questionary.select(
                "I'll search for:\n[press Intro]",
                choices=item_types,
                style=Q_STYLE,
            ).ask()
            
            if not scelta_raw:
                return
            
            # Fix trailing 's' slicing (needed for album/track, but breaks Favorites)
            if scelta_raw == "Favorites":
                selected_type = "favorites"
            else:
                selected_type = scelta_raw[:-1].lower() 
                
            logger.info(f"{YELLOW}Ok, we'll search for {selected_type}{RESET}")
            final_url_list = []
            
            while True:
                if selected_type == "favorites":
                    # --- FAVORITES FLOW: Choose the category instead of typing ---
                    fav_types = ["Albums", "Tracks", "Artists", "Playlists"]
                    selected_fav_raw = questionary.select(
                        "Which favorites do you want to browse?\n[press Intro]",
                        choices=fav_types,
                        style=Q_STYLE,
                    ).ask()
                    
                    if not selected_fav_raw:
                        break
                        
                    selected_fav = selected_fav_raw.lower()
                    
                    logger.info(f"{YELLOW}Fetching your favorite {selected_fav}...{RESET}")
                    options = self.search_by_type(None, selected_type, limit=self.interactive_limit, fav_subtype=selected_fav)
                    query_title = f"My Favorite {selected_fav.title()}"
                else:
                    # --- STANDARD FLOW: Type the keyword ---
                    query = input(f"{CYAN}Enter your search: [Ctrl + c to quit]\n-{DF} ")
                    logger.info(f"{YELLOW}Searching...{RESET}")
                    options = self.search_by_type(query, selected_type, self.interactive_limit)
                    query_title = query.title()
                
                if not options:
                    logger.info(f"{OFF}Nothing found{RESET}")
                    if selected_type == "favorites":
                        break # Prevent infinite loop if there are no favorites
                    continue
                
                # --- CALIBRATED MINIMAL HEADER (Support for Favorites included) ---
                if selected_type in ["album", "track"] or (selected_type == "favorites" and selected_fav in ["albums", "tracks"]):
                    artist_h = "ARTIST".ljust(20)
                    title_h = "TITLE".ljust(35)
                    type_h = "TYPE".ljust(8)
                    year_h = "YEAR".ljust(4)
                    
                    table_header = (
                        f"     {artist_h}   {title_h}   {type_h}   {year_h}   QUALITY\n"
                        f"     {'-' * 88}"
                    )
                else:
                    name_h = "NAME".ljust(50)
                    table_header = (
                        f"     {name_h}   RELEASES\n"
                        f"     {'-' * 63}"
                    )
                # ------------------------------------------------------------------

                title = (
                    f'*** RESULTS FOR "{query_title}" ***\n\n'
                    "[Use arrows to move, <Space> to select, <Enter> to confirm]\n"
                    "Press Ctrl + C to quit. Don't select anything to try another search.\n\n"
                    f"{table_header}"
                )
                
                choices = [
                    questionary.Choice(title=opt.get("text"), value=idx)
                    for idx, opt in enumerate(options)
                ]
                
                selected_indices = questionary.checkbox(
                    title,
                    choices=choices,
                    style=Q_STYLE,
                    instruction="",
                ).ask()
                
                if selected_indices is None:
                    return
                
                if len(selected_indices) > 0:
                    [final_url_list.append(options[i]["url"]) for i in selected_indices]
                    
                    y_n = questionary.select(
                        "Items were added to queue to be downloaded. Keep searching?",
                        choices=["Yes", "No"],
                        style=Q_STYLE,
                    ).ask()
                    if y_n == "No" or y_n is None:
                        break
                else:
                    logger.info(f"{YELLOW}Ok, try again...{RESET}")
                    if selected_type == "favorites":
                        break # Exit if nothing is selected in favorites
                    continue
                    
            if final_url_list:
                desc = "Select [intro] the quality (the quality will be automatically\ndowngraded if the selected is not found)"
                qualities_choices = [
                    questionary.Choice(title=q.get("q_string"), value=q.get("q"))
                    for q in qualities
                ]
                selected_quality = questionary.select(
                    desc,
                    choices=qualities_choices,
                    default=qualities_choices[1],
                    style=Q_STYLE,
                ).ask()
                if selected_quality is None:
                    return
                self.quality = selected_quality

                if download:
                    self.download_list_of_urls(final_url_list)

                return final_url_list
                
        except KeyboardInterrupt:
            logger.info(f"{YELLOW}Bye")
            return

    def download_lastfm_pl(self, playlist_url):
        """
        Parses an external Last.fm playlist, queries the Qobuz database via Fuzzy Matching, 
        and initiates a batch download of all matched tracks.
        """
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
        if not getattr(self, 'playlist_as_albums', False):
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
        if not getattr(self, 'playlist_as_albums', False):
            self.folder_format = original_folder_format
            self.settings.multiple_disc_one_dir = original_multi_disc_setting

        if not self.no_m3u_for_playlists:
            # Keep the order of the Last.fm playlist (the files are matched by track ID)
            make_m3u(pl_directory, [{"id": t_id} for t_id in track_ids])