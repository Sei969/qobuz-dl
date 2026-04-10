from .lyrics_engine import LyricsEngine
import logging
import os
import time
import random
import subprocess
from typing import Tuple
from concurrent.futures import ThreadPoolExecutor

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pathvalidate import sanitize_filename
from tqdm import tqdm

import qobuz_dl.metadata as metadata
from qobuz_dl.color import OFF, GREEN, RED, YELLOW, CYAN
from qobuz_dl.exceptions import NonStreamable

QL_DOWNGRADE = "FormatRestrictedByFormatAvailability"
DEFAULT_FORMATS = {
    "MP3": [
        "{artist} - {album} ({year}) [MP3]",
        "{tracknumber}. {tracktitle}",
    ],
    "Unknown": [
        "{artist} - {album}",
        "{tracknumber}. {tracktitle}",
    ],
}

DEFAULT_FOLDER = "{artist} - {album} ({year}) [{bit_depth}B-{sampling_rate}kHz]"
DEFAULT_TRACK = "{tracknumber}. {tracktitle}"

logger = logging.getLogger(__name__)


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
        no_credits: bool = False, # <-- NEW FLAG
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
        self.no_credits = no_credits # <-- NEW FLAG ASSIGNMENT

        # --- LYRICS ENGINE (Initialization) ---
        self.fetch_lyrics = fetch_lyrics
        if self.fetch_lyrics:
            self.lyrics_engine = LyricsEngine(genius_token)

    def download_id_by_type(self, track=True):
        if not track:
            self.download_release()
        else:
            self.download_track()

    def download_release(self):
        count = 0
        meta = self.client.get_album_meta(self.item_id)

        if not meta.get("streamable"):
            raise NonStreamable("This release is not streamable")

        if self.albums_only and (
            meta.get("release_type") != "album"
            or meta.get("artist").get("name") == "Various Artists"
        ):
            logger.info(f'{OFF}Ignoring Single/EP/VA: {meta.get("title", "n/a")}')
            return

        album_title = _get_title(meta)
        format_info = self._get_format(meta)
        file_format, quality_met, bit_depth, sampling_rate = format_info

        if not self.downgrade_quality and not quality_met:
            logger.info(f"{OFF}Skipping {album_title} as it doesn't meet quality requirement")
            return

        logger.info(f"\n{YELLOW}Downloading: {album_title}\nQuality: {file_format} ({bit_depth}/{sampling_rate})\n")
        
        album_attr = self._get_album_attr(meta, album_title, file_format, bit_depth, sampling_rate)
        folder_format, track_format = _clean_format_str(self.folder_format, self.track_format, file_format)
        sanitized_title = sanitize_filename(folder_format.format(**album_attr))
        dirn = os.path.join(self.path, sanitized_title)
        os.makedirs(dirn, exist_ok=True)

        # --- AUTOMATIC TRACKLIST CREATION ---
        self._generate_tracklist(meta, dirn, album_title, file_format, bit_depth, sampling_rate)

        if self.no_cover:
            logger.info(f"{OFF}Skipping cover")
        else:
            _get_extra(meta["image"]["large"], dirn, og_quality=self.cover_og_quality)

        if "goodies" in meta:
            try:
                _get_extra(meta["goodies"][0]["url"], dirn, "booklet.pdf")
            except:  # noqa
                pass
                
        media_numbers = [track["media_number"] for track in meta["tracks"]["items"]]
        is_multiple = True if len([*{*media_numbers}]) > 1 else False
        
        for i in meta["tracks"]["items"]:
            parse = self.client.get_track_url(i["id"], fmt_id=self.quality)
            if "sample" not in parse and parse["sampling_rate"]:
                is_mp3 = True if int(self.quality) == 5 else False
                
                try:
                    disc_num = int(i.get("media_number", 1))
                except (ValueError, TypeError):
                    disc_num = 1

                self._download_and_tag(
                    dirn,
                    count,
                    parse,
                    i,
                    meta,
                    False,
                    is_mp3,
                    disc_num if is_multiple else None,
                )
            else:
                logger.info(f"{OFF}Demo. Skipping")
            count = count + 1
        logger.info(f"{GREEN}Completed")

    def download_track(self):
        parse = self.client.get_track_url(self.item_id, self.quality)
        if "sample" not in parse and parse["sampling_rate"]:
            meta = self.client.get_track_meta(self.item_id)
            track_title = _get_title(meta)
            logger.info(f"\n{YELLOW}Downloading: {track_title}")
            format_info = self._get_format(meta, is_track_id=True, track_url_dict=parse)
            file_format, quality_met, bit_depth, sampling_rate = format_info

            folder_format, track_format = _clean_format_str(self.folder_format, self.track_format, str(bit_depth))

            if not self.downgrade_quality and not quality_met:
                logger.info(f"{OFF}Skipping {track_title} as it doesn't meet quality requirement")
                return
                
            track_attr = self._get_track_attr(meta, track_title, bit_depth, sampling_rate)
            sanitized_title = sanitize_filename(folder_format.format(**track_attr))

            dirn = os.path.join(self.path, sanitized_title)
            os.makedirs(dirn, exist_ok=True)
            if self.no_cover:
                logger.info(f"{OFF}Skipping cover")
            else:
                _get_extra(meta["album"]["image"]["large"], dirn, og_quality=self.cover_og_quality)
                
            is_mp3 = True if int(self.quality) == 5 else False
            self._download_and_tag(dirn, 1, parse, meta, meta, True, is_mp3, self.embed_art)
        else:
            logger.info(f"{OFF}Demo. Skipping")
        logger.info(f"{GREEN}Completed")

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
    ):
        extension = ".mp3" if is_mp3 else ".flac"
        
        # 1. INTER-TRACK DELAY: Pause to reduce Akamai CDN throttling
        time.sleep(1)

        total_discs = album_or_track_metadata.get('media_count', 1)
        if multiple and total_discs > 1:
            try:
                d_num = int(multiple) if not isinstance(multiple, bool) else 1
            except: d_num = 1
            root_dir = os.path.join(root_dir, f"Disc {d_num}")
        
        if not os.path.exists(root_dir):
            os.makedirs(root_dir, exist_ok=True)

        filename = os.path.join(root_dir, f".{tmp_count:02}.tmp")
        track_title = track_metadata.get("title")
        track_no = str(track_metadata.get('track_number', 0)).zfill(2)
        desc = f"{track_no}. {track_title}"

        # --- CONTROLLED DOWNGRADE LOGIC + SEGMENT DOWNLOAD ---
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
                print(f"{YELLOW}[!] Automatic downgrade: Attempting to save in {TIER_NAMES[attempt_fmt]}...{OFF}")

            try:
                # 1. FAST ATTEMPT (DIRECT URL)
                fresh_track_dict = self.client.get_track_url(track_metadata["id"], fmt_id=attempt_fmt, force_segments=False)
                
                if "url" in fresh_track_dict:
                    try:
                        tqdm_download(fresh_track_dict["url"], filename, desc)
                        success = True
                        final_fmt = attempt_fmt
                        break # Done! Exit the loop.
                    except Exception as e:
                        print(f"{YELLOW}[!] Akamai block detected. Activating fallback segmented download...{OFF}")
                        # 2. SPECIAL INTERVENTION: Fast download failed, request segmented URL
                        fresh_track_dict = self.client.get_track_url(track_metadata["id"], fmt_id=attempt_fmt, force_segments=True)
                
                # If we activated segments, proceed with armored download
                if "url_template" in fresh_track_dict:
                    tqdm_download_segments(fresh_track_dict, filename, desc)
                    success = True
                    final_fmt = attempt_fmt
                    break # Done! Exit the loop.
                else:
                    raise Exception("No valid format returned by the server.")

            except Exception as e:
                # 3. LAST RESORT: If both direct and segments fail, the loop restarts by lowering quality
                pass

            def get_fresh_url(fmt=attempt_fmt):
                return self.client.get_track_url(track_metadata["id"], fmt_id=fmt)

            try:
                fresh_track_dict = get_fresh_url()
                
                # HYBRID: Choice between direct URL (mp3/old servers) or URL Template (new segmented servers)
                if "url" in fresh_track_dict:
                    tqdm_download(fresh_track_dict["url"], filename, desc)
                elif "url_template" in fresh_track_dict:
                    tqdm_download_segments(fresh_track_dict, filename, desc)
                else:
                    raise Exception("Track format not supported by the server (Neither URL nor Template)")
                
                success = True
                final_fmt = attempt_fmt
                break 
            except Exception as e:
                # Failed? No problem, the loop moves to the lower quality
                pass

        if not success:
            print(f"\n{RED}[!] TRACK {track_no} DEFINITIVELY DISCARDED AFTER ALL DOWNGRADES.{OFF}")
            print(f"{YELLOW}[!] Skipping to the next track...{OFF}\n")
            return 

        is_mp3 = True if final_fmt == 5 else False
        extension = ".mp3" if is_mp3 else ".flac"

        artist = _safe_get(track_metadata, "performer", "name")
        filename_attr = self._get_filename_attr(artist, track_metadata, track_title)
        formatted_path = sanitize_filename(self.track_format.format(**filename_attr))
        final_file = os.path.join(root_dir, formatted_path)[:250] + extension

        if os.path.exists(final_file):
            try:
                os.remove(final_file)
            except OSError as err:
                print(f"{YELLOW}[!] Cannot overwrite {final_file}: {err}{OFF}")

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
            )
        except Exception as e:
            print(f"{RED}[!] Error tagging: {e}{OFF}")

        # --- LYRICS ENGINE (Injection) ---
        if getattr(self, 'fetch_lyrics', False) and hasattr(self, 'lyrics_engine'):
            
            search_artist = artist if artist else _safe_get(album_or_track_metadata, "artist", "name", default="Unknown")
            search_album = _safe_get(track_metadata, "album", "title", default="")
            
            self.lyrics_engine.fetch_and_inject(
                file_path=final_file,
                artist=search_artist,
                track=track_title,
                album=search_album
            )

    @staticmethod
    def _get_filename_attr(artist, track_metadata, track_title):
        return {
            "artist": artist,
            "albumartist": _safe_get(track_metadata, "album", "artist", "name", default=artist),
            "bit_depth": track_metadata["maximum_bit_depth"],
            "sampling_rate": track_metadata["maximum_sampling_rate"],
            "tracktitle": track_title,
            "version": track_metadata.get("version"),
            "tracknumber": f"{track_metadata['track_number']:02}",
        }

    @staticmethod
    def _get_track_attr(meta, track_title, bit_depth, sampling_rate):
        return {
            "album": meta["album"]["title"],
            "artist": meta["album"]["artist"]["name"],
            "tracktitle": track_title,
            "year": meta["album"]["release_date_original"].split("-")[0],
            "bit_depth": bit_depth,
            "sampling_rate": sampling_rate,
        }

    @staticmethod
    def _get_album_attr(meta, album_title, file_format, bit_depth, sampling_rate):
        return {
            "artist": meta["artist"]["name"],
            "album": album_title,
            "year": meta["release_date_original"].split("-")[0],
            "format": file_format,
            "bit_depth": bit_depth,
            "sampling_rate": sampling_rate,
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

    # --- TRACKLIST ENGINE ---
    def _generate_tracklist(self, meta, dirn, album_title, file_format, bit_depth, sampling_rate):
        import re
        import textwrap
        
        # --- NO CREDITS FLAG CHECK ---
        if self.no_credits:
            return
        
        # Dynamic filename
        safe_title = sanitize_filename(album_title)
        tracklist_path = os.path.join(dirn, f"{safe_title} - Tracklist.txt")
        
        # If it already exists, skip to speed up
        if os.path.isfile(tracklist_path):
            return

        print(f"{CYAN}[+] Generating Digital Booklet...{OFF}")
        
        # Extract general metadata
        artist_name = _safe_get(meta, "artist", "name", default="Unknown Artist")
        composer = _safe_get(meta, "composer", "name", default="N/A")
        label = _safe_get(meta, "label", "name", default="Independent")
        genre = _safe_get(meta, "genre", "name", default="Unknown Genre")
        release_date = meta.get("release_date_original", "Unknown Date")
        
        try:
            with open(tracklist_path, "w", encoding="utf-8") as f:
                # Extended header
                f.write("=" * 70 + "\n")
                f.write(f"ALBUM     : {album_title}\n")
                if composer != "N/A":
                    f.write(f"COMPOSER  : {composer}\n")
                f.write(f"MAIN ART. : {artist_name}\n")
                f.write(f"LABEL     : {label}\n")
                f.write(f"GENRE     : {genre}\n")
                f.write(f"RELEASE   : {release_date}\n")
                f.write(f"QUALITY   : {file_format} ({bit_depth}-Bit / {sampling_rate} kHz)\n")
                f.write("=" * 70 + "\n\n")

                tracks = meta.get("tracks", {}).get("items", [])
                total_discs = max((track.get("media_number", 1) for track in tracks), default=1)
                current_disc = None 
                
                # Loop through each track
                for track in tracks:
                    # Multi-Disc Logic
                    disc_num = track.get("media_number", 1)
                    if total_discs > 1 and disc_num != current_disc:
                        if current_disc is not None:
                            f.write("\n")
                        f.write(f"--- DISC {disc_num} ---\n\n")
                        current_disc = disc_num

                    # Basic track data
                    t_num = str(track.get("track_number", 0)).zfill(2)
                    t_title = track.get("title", "Unknown Title")
                    
                    # Duration/Timing
                    duration = int(track.get("duration", 0))
                    mins, secs = divmod(duration, 60)
                    dur_str = f"[{mins:02}:{secs:02}]"
                    
                    # 1. Print: Number, Title and Duration right-aligned
                    track_header = f"{t_num}. {t_title}"
                    f.write(f"{track_header:<60} {dur_str}\n")
                    
                    # 2. Print: FULL CREDITS (if present)
                    performers_raw = track.get("performers", "")
                    if performers_raw:
                        # Qobuz sometimes uses newlines (\n), sometimes " - ". We catch both!
                        perf_lines = re.split(r'\r?\n|\s+-\s+', str(performers_raw))
                        for line in perf_lines:
                            if line.strip():
                                f.write(f"    * {line.strip()}\n")
                    else:
                        # Fallback if there are no detailed credits
                        t_artist = _safe_get(track, "performer", "name", default=artist_name)
                        f.write(f"    {t_artist}\n")
                    
                    f.write("\n") # Blank line before the next track
                
                # 3. Print: REVIEW at the end of the file
                description = meta.get("description")
                if description:
                    f.write("\n" + "=" * 70 + "\n")
                    f.write("ALBUM REVIEW / NOTES\n")
                    f.write("=" * 70 + "\n\n")
                    
                    # HTML cleanup (Qobuz often uses tags like <br> or <i> in reviews)
                    clean_desc = re.sub(r'<br\s*/?>', '\n', str(description))
                    clean_desc = re.sub(r'<[^<]+>', '', clean_desc)
                    
                    # Wrap text at 70 characters so it doesn't scroll infinitely to the right
                    paragraphs = clean_desc.split('\n')
                    for p in paragraphs:
                        if p.strip():
                            wrapped_paragraph = textwrap.fill(p.strip(), width=70)
                            f.write(wrapped_paragraph + "\n\n")

            print(f"{GREEN}  L Completed: Digital Booklet.txt (Credits & Review){OFF}")
        except Exception as e:
            print(f"{RED}[!] Error creating booklet: {e}{OFF}")


def tqdm_download(url_or_callable, fname, track_name):
    G = "\033[92m"
    Y = "\033[93m"
    R = "\033[91m"
    C = "\033[96m"
    O = "\033[0m" 

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,*/*;q=0.5",
        "Connection": "keep-alive"
    }

    print(f"{C}[+] In progress: {track_name}{O}")

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

                with open(fname, mode) as file, tqdm(
                    total=total_size,
                    unit="iB",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=f" {G}Downloading{O}",
                    initial=downloaded_size,
                    bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                    leave=True 
                ) as bar:
                    for data in r.iter_content(chunk_size=65536):
                        if data:
                            size = file.write(data)
                            downloaded_size += size
                            bar.update(size)
            
            if downloaded_size >= total_size:
                print(f"{G}  L Completed: {track_name}{O}")
                return 

        except Exception as e:
            if attempt < max_retries - 1:
                wait = backoff_delays[attempt]
                print(f"\n{Y}[!] Server block. Retrying in {wait}s ({attempt+1}/{max_retries})...{O}")
                time.sleep(wait)
            else:
                if os.path.exists(fname):
                    os.remove(fname)
                raise Exception("Definitive timeout")

    if downloaded_size < total_size:
        if os.path.exists(fname): os.remove(fname)
        raise Exception("Incomplete download")

def _get_title(item_dict):
    album_title = item_dict["title"]
    version = item_dict.get("version")
    if version:
        album_title = f"{album_title} ({version})" if version.lower() not in album_title.lower() else album_title
    return album_title

def _get_extra(item, dirn, extra="cover.jpg", og_quality=False):
    extra_file = os.path.join(dirn, extra)
    if os.path.isfile(extra_file):
        logger.info(f"{OFF}{extra} was already downloaded")
        return
    tqdm_download(item.replace("_600.", "_org.") if og_quality else item, extra_file, extra)

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

# ---------------- CRYPTOGRAPHIC AND REMUXING ENGINE ----------------
def tqdm_download_segments(track_url_dict, fname, desc):
    G = "\033[92m"
    O = "\033[0m" 
    
    tmp_fname = fname + ".mp4"
    n_segments = track_url_dict["n_segments"]
    url_template = track_url_dict["url_template"]
    raw_key = track_url_dict["raw_key"]

    # 1. ULTRA-FAST MB CALCULATION (Multithreaded)
    def get_seg_size(seg_num):
        url = url_template.replace("$SEGMENT$", str(seg_num))
        try:
            r = requests.head(url, timeout=5)
            return int(r.headers.get("content-length", 0))
        except:
            return 0

    # We use 8 workers just to calculate the total size in half a second
    total_size = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        total_size = sum(ex.map(get_seg_size, range(n_segments + 1)))

    # 2. FLUID STREAM DOWNLOAD FUNCTION
    def fetch_segment_fluid(seg_num):
        url = url_template.replace("$SEGMENT$", str(seg_num))
        r = requests.get(url, stream=True, timeout=15)
        r.raise_for_status()
        seg_data = bytearray()
        
        # Update the bar fluidly every 64KB downloaded
        for chunk in r.iter_content(chunk_size=65536):
            seg_data.extend(chunk)
            bar.update(len(chunk)) 
        return seg_data

    try:
        # Recreate the beautiful progress bar in Megabytes
        with open(tmp_fname, "wb") as file, tqdm(
            total=total_size,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
            desc=f" {G}Segmented Download{O}",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
        ) as bar:

            # PHASE 1: Download only the first 2 segments sequentially to steal the cryptographic UUID
            segment_uuid = None
            for i in range(2):
                seg_data = fetch_segment_fluid(i)
                if i == 1:
                    segment_uuid = _get_qobuz_segment_uuid(seg_data)
                    if segment_uuid is None:
                        raise ConnectionError(f"Cannot find segment UUID for {fname}")

                decrypted = _decrypt_qobuz_segment(seg_data, raw_key, segment_uuid)
                file.write(decrypted)

            # PHASE 2: THE TURBO. 8 parallel connections updating the bar together!
            if n_segments >= 2:
                with ThreadPoolExecutor(max_workers=8) as executor:
                    for seg_data in executor.map(fetch_segment_fluid, range(2, n_segments + 1)):
                        decrypted = _decrypt_qobuz_segment(seg_data, raw_key, segment_uuid)
                        file.write(decrypted)

        # PHASE 3: Final remuxing
        print(f" {G}  > Assembling the final FLAC file...{O}")
        remux = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", tmp_fname, "-c:a", "copy", "-f", "flac", fname], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if remux.returncode != 0:
            raise ConnectionError(f"FFmpeg remux failed for {fname}")
        
        print(f"{G}  L Completed: {desc}{O}")

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