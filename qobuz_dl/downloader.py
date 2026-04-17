from .lyrics_engine import LyricsEngine
import logging
import os
import sys
import time
import random
import subprocess
import re
import threading
from typing import Tuple
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pathvalidate import sanitize_filename, sanitize_filepath
from tqdm import tqdm

import qobuz_dl.metadata as metadata
from qobuz_dl.color import OFF, GREEN, RED, YELLOW, CYAN
from qobuz_dl.exceptions import NonStreamable
from qobuz_dl.settings import QobuzDLSettings
from qobuz_dl.utils import get_album_artist, clean_filename
from qobuz_dl.db import handle_download_id
from qobuz_dl.constants import DEFAULT_FOLDER, DEFAULT_TRACK, DEFAULT_MULTIPLE_DISC_TRACK, OK_MAX_CHARACTER_LENGTH

# UI Lock to prevent text scrambling during multithreading
print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        text = " ".join(map(str, args))
        end = kwargs.get('end', '\n')
        tqdm.write(text, end=end)

# --- FIX ISSUE #216: Normalizzazione del Release Type ---
def format_release_type(release_type: str) -> str:
    """
    Normalizza il tipo di pubblicazione (release_type) dalle API di Qobuz.
    Converte 'ep' in 'EP', 'single' in 'Single', 'album' in 'Album', ecc.
    Ritorna 'Unknown' come fallback robusto in assenza di dati.
    """
    if not release_type:
        return "Unknown"
    
    release_type = release_type.lower()
    if release_type == "ep":
        return "EP"
        
    return release_type.title()
# --------------------------------------------------------

def process_folder_format_with_subdirs(folder_format, attr_dict, path=None):
    path_parts = folder_format.split('/')
    cleaned_parts = []
    for part in path_parts:
        if part:
            try:
                formatted_part = part.format(**attr_dict)
                cleaned_part = sanitize_filepath(clean_filename(formatted_part), replacement_text="_")
                
                # --- FIX: SMART TRUNCATION FOR ALBUM FOLDER ---
                # Truncate exceptionally long folder names to prevent path length errors in third-party apps
                if cleaned_part and len(cleaned_part) > 120:
                    start_f = cleaned_part[:60].rstrip(' ."-_\'')
                    end_f = cleaned_part[-50:].lstrip(' ."-_\'')
                    cleaned_part = f"{start_f}...{end_f}"
                    
                if cleaned_part:
                    cleaned_parts.append(cleaned_part)
            except KeyError as e:
                logger.warning(f"{YELLOW}Format error ({e}), using original text.{OFF}")
                cleaned_part = sanitize_filepath(clean_filename(part), replacement_text="_")
                
                # Apply truncation to the fallback as well
                if cleaned_part and len(cleaned_part) > 120:
                    start_f = cleaned_part[:60].rstrip(' ."-_\'')
                    end_f = cleaned_part[-50:].lstrip(' ."-_\'')
                    cleaned_part = f"{start_f}...{end_f}"
                    
                if cleaned_part:
                    cleaned_parts.append(cleaned_part)
    
    final_path = os.path.join(*cleaned_parts) if cleaned_parts else ""
    if path is not None:
        return os.path.join(path, final_path)
    return final_path

QL_DOWNGRADE = "FormatRestrictedByFormatAvailability"
DEFAULT_FORMATS = {
    "MP3": [
        "{album_artist} - {album_title} ({year}) [MP3]",
        "{track_number} - {track_title}",
    ],
    "Unknown": [
        "{album_artist} - {album_title}",
        "{track_number} - {track_title}",
    ],
}

EMB_COVER_NAME = "embed_cover.jpg"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Download:
    def __init__(
        self,
        client,
        item_id: str,
        path: str,
        quality: int,
        embed_art: bool = False,
        albums_only: bool = False,
        downgrade_quality: bool = False,
        cover_og_quality: bool = False,
        no_cover: bool = False,
        folder_format=None,
        track_format=None,
        fetch_lyrics: bool = False,
        genius_token: str = None,
        no_credits: bool = False,
        settings: QobuzDLSettings = None,
        download_db=None,
        is_playlist: bool = False,           # <-- NEW
        playlist_track_number: int = None,   # <-- NEW
    ):
        self.client = client
        self.item_id = item_id
        self.path = path
        self.quality = quality
        self.albums_only = albums_only
        self.embed_art = embed_art
        self.downgrade_quality = downgrade_quality
        self.cover_og_quality = cover_og_quality
        self.no_cover = no_cover
        self.folder_format = folder_format or DEFAULT_FOLDER
        self.track_format = track_format or DEFAULT_TRACK
        self.no_credits = no_credits 

        self.fetch_lyrics = fetch_lyrics
        if self.fetch_lyrics:
            self.lyrics_engine = LyricsEngine(genius_token)

        self.settings = settings or QobuzDLSettings()
        self.download_db = download_db
        
        self.is_playlist = is_playlist                       # <-- NEW
        self.playlist_track_number = playlist_track_number   # <-- NEW
        
        self._original_folder_format = folder_format or DEFAULT_FOLDER
        self._original_track_format = track_format or DEFAULT_TRACK
        self._original_multiple_disc_track_format = settings.multiple_disc_track_format if settings else DEFAULT_MULTIPLE_DISC_TRACK

    def download_id_by_type(self, track=True):
        self.folder_format = self._original_folder_format
        self.track_format = self._original_track_format
        if self.settings:
            self.settings.multiple_disc_track_format = self._original_multiple_disc_track_format
        
        if not track:
            self.download_release()
        else:
            self.download_track()

    def download_release(self):
        count = 0
        album_meta = self.client.get_album_meta(self.item_id)

        if not album_meta.get("streamable"):
            raise NonStreamable("This release is not streamable")

        if self.albums_only and (
            album_meta.get("release_type") != "album"
            or album_meta.get("artist").get("name") == "Various Artists"
        ):
            logger.info(f'{OFF}Ignoring Single/EP/VA: {album_meta.get("title", "n/a")}')
            return

        album_title = _get_title(album_meta)
        url = album_meta.get("url", "")
        release_date = album_meta.get("release_date_original", "")

        format_info = self._get_format(album_meta)
        file_format, quality_met, bit_depth, sampling_rate = format_info

        if not self.downgrade_quality and not quality_met:
            logger.info(f"{OFF}Skipping {album_title} as it doesn't meet quality requirement")
            return

        logger.info(
            f"\n{YELLOW}Downloading: {album_title}\nQuality: {file_format}"
            f" ({bit_depth}/{sampling_rate})\n{OFF}"
        )
        
        album_attr = self._get_album_attr(
            album_meta, album_title, file_format, bit_depth, sampling_rate
        )
        
        self._determine_formats(album_meta=album_meta, album_attr=album_attr, tracks_meta=album_meta["tracks"]["items"],
                                track_attr=None, is_track=False, file_format=file_format, settings=self.settings)
        
        dirn = process_folder_format_with_subdirs(self.folder_format, album_attr, self.path)
        os.makedirs(dirn, exist_ok=True)

        self._generate_tracklist(album_meta, dirn, album_title, file_format, bit_depth, sampling_rate)

        if self.settings.no_cover:
            logger.info(f"{OFF}Skipping cover")
        else:
            _get_extra(album_meta["image"]["large"], dirn, art_size=self.settings.saved_art_size)

        if self.settings.embed_art:
            _get_extra(album_meta["image"]["large"], dirn, extra=EMB_COVER_NAME, art_size=self.settings.embedded_art_size)
        else:
            logger.info(f"{OFF}Skipping embedded art")

        if "goodies" in album_meta:
            _download_goodies(album_meta, dirn)
            
        media_count = album_meta.get("media_count", 1)
        is_multiple = True if media_count > 1 else False
        
        # --- SMART SEQUENTIAL vs PARALLEL MODE ---
        delay_time = getattr(self.settings, 'delay', 0)
        if delay_time == 0 and '--delay' in sys.argv:
            try: delay_time = int(sys.argv[sys.argv.index('--delay') + 1])
            except: pass
            
        active_workers = int(getattr(self.settings, 'max_workers', 3))
        is_parallel = False
        
        if delay_time > 0:
            safe_print(f"{YELLOW}[*] Safety Delay active: Multithreading disabled (Sequential mode).{OFF}")
            active_workers = 1
        elif active_workers > 1:
            is_parallel = True
            safe_print(f"{YELLOW}[*] Multithreading Enabled ({active_workers} workers): UI optimized for clean parallel logging.{OFF}")
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=active_workers) as executor:
            futures = []
            for i in album_meta["tracks"]["items"]:
                parse = self.client.get_track_url(i["id"], fmt_id=self.quality)
                if "sample" not in parse and parse["sampling_rate"]:
                    is_mp3 = True if int(self.quality) == 5 else False
                    futures.append(
                        executor.submit(
                            self._download_and_tag,
                            dirn,
                            count,
                            parse,
                            i,
                            album_meta,
                            False,
                            is_mp3,
                            i.get("media_number") if is_multiple else None,
                            is_parallel=is_parallel # Injects the behavior modifier
                        )
                    )
                else:
                    logger.info(f"{OFF}Demo. Skipping")
                count = count + 1
                
            try:
                for f in futures:
                    while not f.done():
                        time.sleep(0.2)
                for f in futures:
                    f.result()
            except KeyboardInterrupt:
                safe_print(f"\n{RED}[!] CTRL+C Detected: Forcing termination of ongoing downloads...{OFF}")
                os._exit(1)
            except Exception as e:
                logger.error(f"{RED}[!] Thread Exception: {e}{OFF}")
            
        _clean_embed_art(dirn, self.settings)
        
        handle_download_id(db_path=self.download_db, item_id=self.item_id, add_id=True, media_type="album",
                           quality=self.quality, file_format=file_format, quality_met=quality_met,
                           bit_depth=bit_depth, sampling_rate=sampling_rate, saved_path=dirn,
                           url=url, release_date=release_date)
        safe_print(f"{GREEN}Completed{OFF}")

    def download_track(self):
        parse = self.client.get_track_url(self.item_id, self.quality)
        if "sample" not in parse and parse["sampling_rate"]:
            track_meta = self.client.get_track_meta(self.item_id)
            
            # --- START PLAYLIST FIX: OVERRIDE TRACK NUMBER ---
            if getattr(self, 'is_playlist', False) and getattr(self, 'playlist_track_number', None):
                track_meta["track_number"] = self.playlist_track_number
            # -------------------------------------------------
            
            track_title = _get_title(track_meta)
            artist = _safe_get(track_meta, "performer", "name")
            logger.info(f"\n{YELLOW}Downloading: {artist} - {track_title}{OFF}")
            url = track_meta.get("album", {}).get("url", "")
            release_date = track_meta.get("release_date_original", "")
            format_info = self._get_format(track_meta, is_track_id=True, track_url_dict=parse)
            file_format, quality_met, bit_depth, sampling_rate = format_info

            folder_format, track_format = _clean_format_str(self.folder_format, self.track_format, str(bit_depth))

            if not self.downgrade_quality and not quality_met:
                logger.info(f"{OFF}Skipping {track_title} as it doesn't meet quality requirement")
                return
                
            track_attr = self._get_track_attr(
                track_meta, track_title, bit_depth, sampling_rate, file_format
            )
            
            self._determine_formats(album_meta=track_meta.get("album", {}), album_attr=None, tracks_meta=[track_meta],
                                    track_attr=track_attr, is_track=True, file_format=file_format, settings=self.settings)
            
            dirn = process_folder_format_with_subdirs(self.folder_format, track_attr, self.path)
            os.makedirs(dirn, exist_ok=True)

            # --- START PLAYLIST COVER FIX ---
            if getattr(self, 'is_playlist', False):
                # Skip saving the generic cover.jpg to avoid cluttering the folder with 50 different images
                logger.info(f"{OFF}Skipping standard cover save to keep playlist folder clean")
            elif self.settings.no_cover:
                logger.info(f"{OFF}Skipping cover")
            else:
                _get_extra(track_meta["album"]["image"]["large"], dirn, art_size=self.settings.saved_art_size)

            if self.settings.embed_art:
                # Force remove previous embedded cover to prevent caching issues across tracks
                embed_path = os.path.join(dirn, EMB_COVER_NAME)
                if os.path.exists(embed_path):
                    try:
                        os.remove(embed_path)
                    except OSError:
                        pass
                
                _get_extra(track_meta["album"]["image"]["large"], dirn, extra=EMB_COVER_NAME,
                           art_size=self.settings.embedded_art_size)
            else:
                logger.info(f"{OFF}Skipping embedded art")
            # --- END PLAYLIST COVER FIX ---
                
            is_mp3 = True if int(self.quality) == 5 else False
            
            self._download_and_tag(
                dirn,
                1,
                parse,
                track_meta,
                track_meta,
                True,
                is_mp3,
                False,
                is_parallel=False
            )
            
            _clean_embed_art(dirn, self.settings)
            
            handle_download_id(db_path=self.download_db, item_id=self.item_id, add_id=True, media_type="track",
                               quality=self.quality, file_format=file_format, quality_met=quality_met,
                               bit_depth=bit_depth, sampling_rate=sampling_rate, saved_path=dirn,
                               url=url, release_date=release_date)
        else:
            logger.info(f"{OFF}Demo. Skipping")
        logger.info(f"{GREEN}Completed{OFF}")

    def _download_and_tag(
        self,
        root_dir,
        tmp_count,
        track_url_dict,
        track_metadata,
        album_or_track_metadata,
        is_track,
        is_mp3,
        multiple=None,
        is_parallel=False
    ):
        extension = ".mp3" if is_mp3 else ".flac"
        time.sleep(1)

        try:
            url = track_url_dict["url"]
        except KeyError:
            logger.info(f"{OFF}Track not available for download")
            return

        total_discs = album_or_track_metadata.get('media_count', 1)
        if multiple and total_discs > 1 and (not self.settings.multiple_disc_one_dir):
            try:
                d_num = int(multiple) if not isinstance(multiple, bool) else 1
            except (ValueError, TypeError): 
                d_num = 1
            root_dir = os.path.join(root_dir, f"{self.settings.multiple_disc_prefix} {d_num:02}")
        
        if not os.path.exists(root_dir):
            os.makedirs(root_dir, exist_ok=True)

        filename = os.path.join(root_dir, f".{tmp_count:02}.tmp")
        track_title = track_metadata.get("title")
        track_no = str(track_metadata.get('track_number', 0)).zfill(2)
        desc = f"{track_no}. {track_title}"

        FALLBACK_TIERS = [27, 7, 6, 5]
        TIER_NAMES = {27: "24-bit/>96kHz", 7: "24-bit/96kHz", 6: "16-bit/44.1kHz (CD)", 5: "MP3 320kbps"}
        
        try:
            start_idx = FALLBACK_TIERS.index(int(self.quality))
        except ValueError:
            start_idx = 0
            
        qualities_to_try = FALLBACK_TIERS[start_idx:]
        success = False
        final_fmt = int(self.quality)

        for attempt_fmt in qualities_to_try:
            if attempt_fmt != int(self.quality):
                safe_print(f"{YELLOW}[!] Automatic downgrade: Attempting to save in {TIER_NAMES[attempt_fmt]}...{OFF}")

            def get_fresh_url(fmt=attempt_fmt, force_segments=False):
                return self.client.get_track_url(track_metadata["id"], fmt_id=fmt, force_segments=force_segments)

            try:
                fresh_track_dict = get_fresh_url(force_segments=False)
                
                if "url" in fresh_track_dict:
                    try:
                        tqdm_download(fresh_track_dict["url"], filename, desc, is_parallel=is_parallel)
                        success = True
                        final_fmt = attempt_fmt
                        break
                    except Exception as e:
                        safe_print(f"{YELLOW}[!] Akamai block detected. Activating fallback segmented download...{OFF}")
                        fresh_track_dict = get_fresh_url(force_segments=True)
                
                if "url_template" in fresh_track_dict:
                    tqdm_download_segments(fresh_track_dict, filename, desc, is_parallel=is_parallel)
                    success = True
                    final_fmt = attempt_fmt
                    break
                elif not success:
                    raise Exception("No valid format returned by the server.")

            except Exception as e:
                pass

        if not success:
            safe_print(f"\n{RED}[!] TRACK {track_no} DEFINITIVELY DISCARDED AFTER ALL DOWNGRADES.{OFF}")
            safe_print(f"{YELLOW}[!] Skipping to the next track...{OFF}\n")
            return 

        is_mp3 = True if final_fmt == 5 else False
        extension = ".mp3" if is_mp3 else ".flac"

        track_artist = _safe_get(track_metadata, "performer", "name")
        filename_attr = self._get_filename_attr(
            track_artist,
            track_metadata,
            album_or_track_metadata.get("album", {}) if is_track else album_or_track_metadata
        )

        if multiple and self.settings.multiple_disc_one_dir:
            formatted_path = sanitize_filename(clean_filename(self.settings.multiple_disc_track_format.format(**filename_attr)), replacement_text="_")
        else:
            formatted_path = sanitize_filename(clean_filename(self.track_format.format(**filename_attr)), replacement_text="_")
            
        # --- FIX: SMART TRUNCATION (RISOLUZIONE DEFINITIVA) ---
        # Sganciamo il calcolo dalla cartella. Un singolo nome file può arrivare a 255 caratteri.
        # Fissiamo un limite iper-sicuro di 180 caratteri totali per la traccia.
        max_len = 180
        
        if len(formatted_path) > max_len:
            # Conserva i primi 110 caratteri e gli ultimi 60.
            # .rstrip() e .lstrip() ripuliscono istantaneamente apici, trattini o spazi tagliati a metà.
            inizio = formatted_path[:110].rstrip(' ."-_\'')
            fine = formatted_path[-60:].lstrip(' ."-_\'')
            formatted_path = f"{inizio}...{fine}"
            
        final_file = os.path.join(root_dir, formatted_path) + extension

        if os.path.exists(final_file):
            try:
                os.remove(final_file)
            except OSError as err:
                safe_print(f"{YELLOW}[!] Cannot overwrite {final_file}: {err}{OFF}")

        tag_function = metadata.tag_mp3 if is_mp3 else metadata.tag_flac
        try:
            tag_function(
                filename,
                root_dir,
                final_file,
                track_metadata,
                album_or_track_metadata,
                is_track,
                self.embed_art,
                settings=self.settings,
            )
        except Exception as e:
            safe_print(f"{RED}[!] Error tagging: {e}{OFF}")

        if getattr(self, 'fetch_lyrics', False) and hasattr(self, 'lyrics_engine'):
            search_artist = _safe_get(track_metadata, "performer", "name") or _safe_get(album_or_track_metadata, "artist", "name", default="Unknown")
            search_album = _safe_get(track_metadata, "album", "title", default="")
            
            with print_lock:
                self.lyrics_engine.fetch_and_inject(
                    file_path=final_file,
                    artist=search_artist,
                    track=track_title,
                    album=search_album
                )

        # --- HUMAN BEHAVIOR DELAY ---
        delay_time = getattr(self.settings, 'delay', 0)
        if delay_time == 0 and '--delay' in sys.argv:
            try:
                delay_time = int(sys.argv[sys.argv.index('--delay') + 1])
            except: pass
            
        if delay_time > 0:
            safe_print(f"{YELLOW}[*] Sleeping for {delay_time} seconds to prevent rate limiting...{OFF}")
            time.sleep(delay_time)

    @staticmethod
    def _get_filename_attr(track_artist, track_metadata: dict, album_metadata: dict):     
           
        return {
            "artist": track_artist,
            "albumartist": get_album_artist(album_metadata) if get_album_artist(album_metadata) else track_artist,
            "tracktitle": _get_title(track_metadata),
            "album_title":  _get_title(album_metadata),
            "album_title_base": album_metadata.get("title"),
            "album_artist": get_album_artist(album_metadata) if get_album_artist(album_metadata) else track_artist,
            "track_id": track_metadata.get("id"),
            "track_artist": track_artist,
            "track_composer": _safe_get(track_metadata,"composer", "name"),
            "track_number": f'{track_metadata.get("track_number", 0):02}',
            "isrc": track_metadata.get("isrc"),
            "bit_depth": track_metadata.get("maximum_bit_depth"),
            "sampling_rate": track_metadata.get("maximum_sampling_rate"),
            "track_title": _get_title(track_metadata),
            "track_title_base": track_metadata.get("title"),
            "version": track_metadata.get("version"),
            "year": track_metadata.get("release_date_original").split("-")[0],
            "disc_number": f'{track_metadata.get("media_number"):02}',
            "release_date": track_metadata.get("release_date_original"),
            "ExplicitFlag": "[E]" if track_metadata.get("parental_warning") else "",
            "explicit": "[E]" if track_metadata.get("parental_warning") else "",
        }

    @staticmethod
    def _get_track_attr(meta, track_title, bit_depth, sampling_rate, file_format):
        album_meta = meta.get("album", {})
        return {
            "album": _get_title(album_meta),
            "artist": get_album_artist(album_meta) if get_album_artist(album_meta) else _safe_get(meta, "performer", "name"),
            "tracktitle": track_title,
            "track_title": track_title,
            "track_title_base": meta.get("title", ""),
            "album_id": meta.get("id", ""),
            "album_url": meta.get("url", ""),
            "album_title": _get_title(album_meta),
            "album_title_base": album_meta.get("title", ""),
            "album_artist": get_album_artist(album_meta) if get_album_artist(album_meta) else _safe_get(meta, "performer", "name"),
            "album_genre": meta.get("genre", {}).get("name", ""),
            "album_composer": meta.get("composer", {}).get("name", ""),
            "label": re.sub(r'\s*[\;\/]\s*|\s+\-\s+',' ／ ', ' '.join(meta.get("label",{}).get("name", "").split())).strip(),
            "copyright": meta.get("copyright", ""),
            "upc": meta.get("upc", ""),
            "barcode": meta.get("upc", ""),
            "release_date": meta.get("release_date_original", ""),
            "year": meta.get("release_date_original", "").split("-")[0],
            "media_type": meta.get("product_type", "").capitalize(),
            "format": file_format,
            "bit_depth": bit_depth,
            "sampling_rate": sampling_rate,
            "album_version": meta.get("version", ""),
            "version_tag": f" - {meta.get('version')}" if meta.get("version") else "",
            "disc_count": meta.get("media_count", ""),
            "track_count": meta.get("track_count", ""),
            "ExplicitFlag": "[E]" if album_meta.get("parental_warning") else "",
            "explicit": "[E]" if album_meta.get("parental_warning") else "",
            # --- FIX ISSUE #216 ---
            "release_type": format_release_type(album_meta.get("release_type")),
        }

    @staticmethod
    def _get_album_attr(meta, album_title, file_format, bit_depth, sampling_rate):
        return {
            "artist": meta.get("artist", {}).get("name", ""),
            "album": album_title,
            "album_id": meta.get("id", ""),
            "album_url": meta.get("url", ""),
            "album_title": album_title,
            "album_title_base": meta.get("title", ""),
            "album_artist": get_album_artist(meta),
            "album_genre": meta.get("genre", {}).get("name", ""),
            "album_composer": meta.get("composer", {}).get("name", ""),
            "label": re.sub(r'\s*[\;\/]\s*|\s+\-\s+',' ∕ ', ' '.join(meta.get("label",{}).get("name", "").split())).strip(),
            "copyright": meta.get("copyright", ""),
            "upc": meta.get("upc", ""),
            "barcode": meta.get("upc", ""),
            "release_date": meta.get("release_date_original", ""),
            "year": meta.get("release_date_original", "").split("-")[0],
            "media_type": meta.get("product_type", "").capitalize(),
            "format": file_format,
            "bit_depth": bit_depth,
            "sampling_rate": sampling_rate,
            "album_version": meta.get("version", ""),
            "version_tag": f" - {meta.get('version')}" if meta.get("version") else "",
            "disc_count": meta.get("media_count", 1),
            "track_count": meta.get("track_count", 1),
            "ExplicitFlag": "[E]" if meta.get("parental_warning") else "",
            "explicit": "[E]" if meta.get("parental_warning") else "",
            # --- FIX ISSUE #216 ---
            "release_type": format_release_type(meta.get("release_type")),
        }

    def _get_format(self, item_dict, is_track_id=False, track_url_dict=None):
        quality_met = True
        if int(self.quality) == 5:
            return ("MP3", quality_met, None, None)
        track_dict = item_dict
        if not is_track_id:
            track_dict = item_dict["tracks"]["items"][0]

        try:
            new_track_dict = (
                self.client.get_track_url(track_dict["id"], fmt_id=self.quality)
                if not track_url_dict
                else track_url_dict
            )
            restrictions = new_track_dict.get("restrictions")
            if isinstance(restrictions, list):
                if any(restriction.get("code") == QL_DOWNGRADE for restriction in restrictions):
                    quality_met = False

            return ("FLAC", quality_met, new_track_dict["bit_depth"], new_track_dict["sampling_rate"])
        except (KeyError, requests.exceptions.HTTPError):
            return ("Unknown", quality_met, None, None)

    def _determine_formats(self, album_meta, album_attr, tracks_meta, track_attr, is_track, file_format, settings: QobuzDLSettings):
        format_combinations = [
            (self._original_folder_format, self._original_track_format, self._original_multiple_disc_track_format),
            (settings.fallback_folder_format, self._original_track_format, self._original_multiple_disc_track_format),
            (settings.fallback_folder_format, DEFAULT_TRACK, DEFAULT_MULTIPLE_DISC_TRACK),
            (DEFAULT_FOLDER, DEFAULT_TRACK, DEFAULT_MULTIPLE_DISC_TRACK)
        ]

        media_count = album_meta.get("media_count", 1)
        is_multiple = True if media_count > 1 else False
        extension = ".flac" if file_format.lower() == "flac" else ".mp3"

        for folder_fmt, track_fmt, multi_disc_fmt in format_combinations:
            folder_fmt, track_fmt = _clean_format_str(folder_fmt, track_fmt, file_format)
            valid_combination = True
            
            try:
                if is_track:
                    root_dir = process_folder_format_with_subdirs(folder_fmt, track_attr)
                else:
                    root_dir = process_folder_format_with_subdirs(folder_fmt, album_attr)

                for track_metadata in tracks_meta:
                    track_artist = _safe_get(track_metadata, "performer", "name")
                    filename_attr = self._get_filename_attr(track_artist, track_metadata, album_meta)

                    curr_root_dir = root_dir
                    if is_multiple and self.settings.multiple_disc_one_dir:
                        track_path = sanitize_filename(clean_filename(multi_disc_fmt.format(**filename_attr)), replacement_text="_")
                    else:
                        if is_multiple and not self.settings.multiple_disc_one_dir:
                            disc_dir = f"{self.settings.multiple_disc_prefix} {track_metadata['media_number']:02}"
                            curr_root_dir = os.path.join(root_dir, disc_dir)
                        
                        track_path = sanitize_filename(clean_filename(track_fmt.format(**filename_attr)), replacement_text="_")

                    final_path = os.path.join(curr_root_dir, track_path + extension)
                    
                    if len(final_path) > OK_MAX_CHARACTER_LENGTH:
                        valid_combination = False
                        break
            except (KeyError, ValueError):
                valid_combination = False
                continue

            if valid_combination:
                self.folder_format = folder_fmt
                self.track_format = track_fmt
                if self.settings:
                    self.settings.multiple_disc_track_format = multi_disc_fmt
                return

        self.folder_format = DEFAULT_FOLDER
        self.track_format = DEFAULT_TRACK

    def _generate_tracklist(self, meta, dirn, album_title, file_format, bit_depth, sampling_rate):
        import re
        import textwrap
        
        if self.no_credits:
            return
        
        safe_title = sanitize_filename(album_title)
        tracklist_path = os.path.join(dirn, f"{safe_title} - Tracklist.txt")
        
        if os.path.isfile(tracklist_path):
            return
            
        safe_print(f"{CYAN}[+] Generating Digital Booklet...{OFF}")
        
        artist_name = _safe_get(meta, "artist", "name", default="Unknown Artist")
        composer = _safe_get(meta, "composer", "name", default="N/A")
        label = _safe_get(meta, "label", "name", default="Independent")
        genre = _safe_get(meta, "genre", "name", default="Unknown Genre")
        release_date = meta.get("release_date_original", "Unknown Date")
        
        try:
            with open(tracklist_path, "w", encoding="utf-8") as f:
                f.write("=" * 70 + "\n")
                f.write(f"ALBUM      : {album_title}\n")
                if composer != "N/A":
                    f.write(f"COMPOSER   : {composer}\n")
                f.write(f"MAIN ART.  : {artist_name}\n")
                f.write(f"LABEL      : {label}\n")
                f.write(f"GENRE      : {genre}\n")
                f.write(f"RELEASE    : {release_date}\n")
                f.write(f"QUALITY    : {file_format} ({bit_depth}-Bit / {sampling_rate} kHz)\n")
                f.write("=" * 70 + "\n\n")
                
                tracks = meta.get("tracks", {}).get("items", [])
                total_discs = max((track.get("media_number", 1) for track in tracks), default=1)
                current_disc = None 
                
                for track in tracks:
                    disc_num = track.get("media_number", 1)
                    if total_discs > 1 and disc_num != current_disc:
                        if current_disc is not None:
                            f.write("\n")
                        f.write(f"--- DISC {disc_num} ---\n\n")
                        current_disc = disc_num

                    t_num = str(track.get("track_number", 0)).zfill(2)
                    t_title = track.get("title", "Unknown Title")
                    
                    duration = int(track.get("duration", 0))
                    mins, secs = divmod(duration, 60)
                    dur_str = f"[{mins:02}:{secs:02}]"
                    
                    track_header = f"{t_num}. {t_title}"
                    f.write(f"{track_header:<60} {dur_str}\n")
                    
                    performers_raw = track.get("performers", "")
                    if performers_raw:
                        perf_lines = re.split(r'\r?\n|\s+-\s+', str(performers_raw))
                        for line in perf_lines:
                            if line.strip():
                                f.write(f"    * {line.strip()}\n")
                    else:
                        t_artist = _safe_get(track, "performer", "name", default=artist_name)
                        f.write(f"    {t_artist}\n")
                    
                    f.write("\n")
                
                description = meta.get("description")
                if description:
                    f.write("\n" + "=" * 70 + "\n")
                    f.write("ALBUM REVIEW / NOTES\n")
                    f.write("=" * 70 + "\n\n")
                    
                    clean_desc = re.sub(r'<br\s*/?>', '\n', str(description))
                    clean_desc = re.sub(r'<[^<]+>', '', clean_desc)
                    
                    paragraphs = clean_desc.split('\n')
                    for p in paragraphs:
                        if p.strip():
                            wrapped_paragraph = textwrap.fill(p.strip(), width=70)
                            f.write(wrapped_paragraph + "\n\n")

            safe_print(f"{GREEN}  L Completed: Digital Booklet.txt (Credits & Review){OFF}")
        except Exception as e:
            safe_print(f"{RED}[!] Error creating booklet: {e}{OFF}")


def _get_description(item: dict, track_title, multiple=None):
    downloading_title = f"{track_title} [{item.get('bit_depth', '')}/{item.get('sampling_rate', '')}]"
    if multiple:
        downloading_title = f"[CD {multiple}] {downloading_title}"
    return downloading_title

def tqdm_download(url_or_callable, fname, track_name, is_parallel=False):
    G = "\033[92m"
    Y = "\033[93m"
    C = "\033[96m"
    O = "\033[0m"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,*/*;q=0.5",
        "Connection": "keep-alive"
    }

    if not is_parallel:
        safe_print(f"{C}[+] In progress: {track_name}{O}")
        tqdm_desc = f" {G}Downloading{O}"
        b_format = "{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
    else:
        tqdm_desc = ""
        b_format = ""

    downloaded_size = 0
    total_size = 0
    max_retries = 5
    backoff_delays = [2, 4, 8, 16, 32] 

    for attempt in range(max_retries):
        try:
            url = url_or_callable() if callable(url_or_callable) else url_or_callable

            if downloaded_size > 0:
                headers['Range'] = f'bytes={downloaded_size}-'
                mode = 'ab'
            else:
                headers['Range'] = 'bytes=0-'
                mode = 'wb'
            
            with requests.Session() as s:
                r = s.get(url, allow_redirects=True, stream=True, headers=headers, timeout=(10, 60))
                
                if r.status_code == 416: return 
                if r.status_code not in [200, 206]:
                    raise Exception(f"Status Server: {r.status_code}")

                if total_size == 0:
                    total_size = downloaded_size + int(r.headers.get('content-length', 0))

                if is_parallel and downloaded_size == 0 and attempt == 0:
                    size_mb = total_size / (1024 * 1024)
                    safe_print(f"{C}[+] In progress: {track_name} [{size_mb:.1f} MB]{O}")

                with open(fname, mode) as file, tqdm(
                    total=total_size,
                    unit="iB",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=tqdm_desc,
                    initial=downloaded_size,
                    bar_format=b_format,
                    leave=False,
                    disable=is_parallel
                ) as bar:
                    for data in r.iter_content(chunk_size=65536):
                        if data:
                            size = file.write(data)
                            downloaded_size += size
                            bar.update(size)
            
            if downloaded_size >= total_size:
                safe_print(f"{G}  L Completed: {track_name}{O}")
                return 

        except Exception:
            if attempt < max_retries - 1:
                wait = backoff_delays[attempt]
                safe_print(f"\n{Y}[!] Server block. Retrying in {wait}s ({attempt+1}/{max_retries})...{O}")
                time.sleep(wait)
            else:
                if os.path.exists(fname):
                    os.remove(fname)
                raise Exception("Definitive timeout")

    if downloaded_size < total_size:
        if os.path.exists(fname): os.remove(fname)
        raise Exception("Incomplete download")

def _get_title(item_dict):
    item_title = item_dict.get("title")
    version = item_dict.get("version")
    if version:
        item_title = (
            f"{item_title} ({version})"
            if version.lower() not in item_title.lower()
            else item_title
        )
    return item_title


def _get_extra(item, dirn, extra="cover.jpg", art_size=None, og_quality=False):
    extra_file = os.path.join(dirn, extra)
    if os.path.isfile(extra_file):
        logger.info(f"{OFF}{extra} was already downloaded")
        return
        
    if og_quality:
        art_size = "org"

    if art_size in ["50", "100", "150", "300", "600", "max", "org"]:
        item = item.replace("_600.", f"_{art_size}.")
        
    tqdm_download(item, extra_file, extra, is_parallel=False)

def _clean_format_str(folder: str, track: str, file_format: str) -> Tuple[str, str]:
    final = []
    for i, fs in enumerate((folder, track)):
        if fs.endswith(".mp3"): fs = fs[:-4]
        elif fs.endswith(".flac"): fs = fs[:-5]
        fs = fs.strip()

        if file_format in ("MP3", "Unknown") and ("bit_depth" in fs or "sampling_rate" in fs):
            default = DEFAULT_FORMATS[file_format][i]
            logger.error(f"{RED}invalid format string for format {file_format}. defaulting to {default}")
            fs = default
        final.append(fs)
    return tuple(final)

def _safe_get(d: dict, *keys, default=None):
    curr = d
    res = default
    for key in keys:
        res = curr.get(key, default)
        if res == default or not hasattr(res, "__getitem__"):
            return res
        else:
            curr = res
    return res

def tqdm_download_segments(track_url_dict, fname, track_name, is_parallel=False):
    G = "\033[92m"
    O = "\033[0m" 
    C = "\033[96m"
    
    tmp_fname = fname + ".mp4"
    n_segments = track_url_dict["n_segments"]
    url_template = track_url_dict["url_template"]
    raw_key = track_url_dict["raw_key"]

    def get_seg_size(seg_num):
        url = url_template.replace("$SEGMENT$", str(seg_num))
        try:
            r = requests.head(url, timeout=5)
            return int(r.headers.get("content-length", 0))
        except:
            return 0

    total_size = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures_size = [ex.submit(get_seg_size, i) for i in range(n_segments + 1)]
        try:
            for f in futures_size:
                while not f.done():
                    time.sleep(0.1)
                total_size += f.result()
        except KeyboardInterrupt:
            os._exit(1)

    if is_parallel:
        size_mb = total_size / (1024 * 1024)
        safe_print(f"{C}[+] In progress: {track_name} [{size_mb:.1f} MB]{O}")
        tqdm_desc = ""
        b_format = ""
    else:
        safe_print(f"{C}[+] In progress: {track_name}{O}")
        tqdm_desc = f" {G}Segmented Download{O}"
        b_format = "{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"

    def fetch_segment_fluid(seg_num):
        url = url_template.replace("$SEGMENT$", str(seg_num))
        r = requests.get(url, stream=True, timeout=15)
        r.raise_for_status()
        seg_data = bytearray()
        
        for chunk in r.iter_content(chunk_size=65536):
            seg_data.extend(chunk)
            if not is_parallel:
                bar.update(len(chunk)) 
        return seg_data

    try:
        with open(tmp_fname, "wb") as file, tqdm(
            total=total_size,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
            desc=tqdm_desc,
            bar_format=b_format,
            leave=False,
            disable=is_parallel
        ) as bar:

            segment_uuid = None
            for i in range(2):
                seg_data = fetch_segment_fluid(i)
                if i == 1:
                    segment_uuid = _get_qobuz_segment_uuid(seg_data)
                    if segment_uuid is None:
                        raise ConnectionError(f"Cannot find segment UUID for {fname}")

                decrypted = _decrypt_qobuz_segment(seg_data, raw_key, segment_uuid)
                file.write(decrypted)

            if n_segments >= 2:
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures_seg = [executor.submit(fetch_segment_fluid, i) for i in range(2, n_segments + 1)]
                    try:
                        for f in futures_seg:
                            while not f.done():
                                time.sleep(0.2)
                            seg_data = f.result()
                            decrypted = _decrypt_qobuz_segment(seg_data, raw_key, segment_uuid)
                            file.write(decrypted)
                    except KeyboardInterrupt:
                        os._exit(1)

        if not is_parallel:
            safe_print(f" {G}  > Assembling the final FLAC file...{O}")
            
        remux = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", tmp_fname, "-c:a", "copy", "-f", "flac", fname], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if remux.returncode != 0:
            raise ConnectionError(f"FFmpeg remux failed for {fname}")
        
        safe_print(f"{G}  L Completed: {track_name}{O}")

    finally:
        if os.path.isfile(tmp_fname):
            os.remove(tmp_fname)


def _get_qobuz_segment_uuid(segment_data):
    pos = 0
    while pos + 24 <= len(segment_data):
        size = int.from_bytes(segment_data[pos : pos + 4], "big")
        if size <= 0 or pos + size > len(segment_data):
            break

        if bytes(segment_data[pos + 4 : pos + 8]) == b"uuid":
            return bytes(segment_data[pos + 8 : pos + 24])
        pos += size
    return None


def _decrypt_qobuz_segment(segment_data, raw_key, segment_uuid):
    if segment_uuid is None:
        return bytes(segment_data)

    buf = bytearray(segment_data)
    pos = 0
    while pos + 8 <= len(buf):
        size = int.from_bytes(buf[pos : pos + 4], "big")
        if size <= 0 or pos + size > len(buf):
            break

        if (
            bytes(buf[pos + 4 : pos + 8]) == b"uuid"
            and bytes(buf[pos + 8 : pos + 24]) == segment_uuid
        ):
            pointer = pos + 28
            data_end = pos + int.from_bytes(buf[pointer : pointer + 4], "big")
            pointer += 4
            counter_len = buf[pointer]
            pointer += 1
            frame_count = int.from_bytes(buf[pointer : pointer + 3], "big")
            pointer += 3

            for _ in range(frame_count):
                frame_len = int.from_bytes(buf[pointer : pointer + 4], "big")
                pointer += 6
                flags = int.from_bytes(buf[pointer : pointer + 2], "big")
                pointer += 2
                frame_start = data_end
                frame_end = frame_start + frame_len
                data_end = frame_end

                if flags:
                    counter = bytes(buf[pointer : pointer + counter_len]) + (
                        b"\x00" * (16 - counter_len)
                    )
                    decryptor = Cipher(
                        algorithms.AES(raw_key), modes.CTR(counter)
                    ).decryptor()
                    buf[frame_start:frame_end] = decryptor.update(
                        bytes(buf[frame_start:frame_end])
                    ) + decryptor.finalize()
                pointer += counter_len
        pos += size
    return bytes(buf)

def _download_goodies(album_meta, dirn):
    try:
        for goody in album_meta.get("goodies", []):
            if not goody.get("url"):
                logger.warning("No URL found for the goody, skipping.")
                continue
            goody_name = sanitize_filename(clean_filename(f'{album_meta.get("title")} ({goody.get("id")}).pdf'))
            _get_extra(goody.get("url"), dirn, extra=goody_name)
    except:
        logger.error(f"{RED}Error downloading goodies", exc_info=True)


def _clean_embed_art(dirn, settings=None):
    embed_file = os.path.join(dirn, EMB_COVER_NAME)
    if os.path.exists(embed_file):
        try:
            time.sleep(0.5) # Ensures metadata taggers release the file on Windows
            os.remove(embed_file)
        except Exception:
            pass