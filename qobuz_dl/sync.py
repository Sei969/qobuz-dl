import os
import logging
import time
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from qobuz_dl.db import handle_download_id
from qobuz_dl.color import GREEN, RED, YELLOW, CYAN, OFF

logger = logging.getLogger(__name__)

def sync_database(directory, db_path, client):
    """
    Scans the local directory and restores missing Qobuz IDs into the local DB.
    Uses embedded custom tags or falls back to Reverse Lookup via Qobuz API with anti-ban delay.
    """
    logger.info(f"\n{YELLOW}[*] Starting Local Database Synchronization...{OFF}")
    logger.info(f"{YELLOW}[*] Scanning directory: {directory}{OFF}")

    # --- PATCH OS.WALK: Immune a parentesi quadre e case-insensitive ---
    all_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.flac', '.mp3')):
                all_files.append(os.path.join(root, file))
    # -------------------------------------------------------------------

    if not all_files:
        logger.info(f"{YELLOW}[!] No audio files found in {directory}.{OFF}")
        return

    logger.info(f"{YELLOW}[*] Found {len(all_files)} audio files. Processing tags...{OFF}")

    added_tracks = 0
    added_albums = set()

    try:
        for file_path in all_files:
            track_id = None
            album_id = None
            isrc = None
            quality = 27
            file_format = "FLAC" if file_path.lower().endswith(".flac") else "MP3"

            try:
                if file_path.lower().endswith(".flac"):
                    audio = FLAC(file_path)
                    
                    # --- RICERCA GERARCHICA FLAC (Stealth -> Legacy) ---
                    track_id_list = audio.get("QDL_TRACK_ID") or audio.get("QOBUZTRACKID") or [None]
                    track_id = track_id_list[0]
                    
                    album_id_list = audio.get("QDL_ALBUM_ID") or audio.get("QOBUZALBUMID") or [None]
                    album_id = album_id_list[0]
                    
                    isrc = audio.get("isrc", [None])[0]
                    
                elif file_path.lower().endswith(".mp3"):
                    audio = ID3(file_path)
                    
                    # --- RICERCA GERARCHICA MP3 (Stealth -> Legacy) ---
                    track_txxx = audio.get("TXXX:QDL_TRACK_ID") or audio.get("TXXX:qdl_track_id") or audio.get("TXXX:QOBUZTRACKID")
                    if track_txxx: track_id = track_txxx.text[0]
                    
                    album_txxx = audio.get("TXXX:QDL_ALBUM_ID") or audio.get("TXXX:qdl_album_id") or audio.get("TXXX:QOBUZALBUMID")
                    if album_txxx: album_id = album_txxx.text[0]
                    
                    tsrc = audio.get("TSRC")
                    if tsrc: isrc = tsrc.text[0]
                
                # --- REVERSE LOOKUP VIA API FOR OLD FILES ---
                if not track_id and isrc:
                    logger.info(f"{CYAN}[*] Missing local ID. Fetching via API (ISRC: {isrc})...{OFF}")
                    res = client.search_tracks(isrc, limit=1)
                    if res and "tracks" in res and res["tracks"]["items"]:
                        q_track = res["tracks"]["items"][0]
                        track_id = str(q_track["id"])
                        album_id = str(q_track.get("album", {}).get("id", ""))
                    
                    # Human behavior delay to prevent Qobuz API throttling and hanging
                    time.sleep(0.2)
                
                # Inject Track ID into DB
                if track_id:
                    handle_download_id(
                        db_path=db_path, item_id=track_id, add_id=True, media_type="track",
                        quality=quality, file_format=file_format, saved_path=file_path
                    )
                    added_tracks += 1
                
                # Inject Album ID into DB
                if album_id and album_id not in added_albums:
                    handle_download_id(
                        db_path=db_path, item_id=album_id, add_id=True, media_type="album",
                        quality=quality, file_format=file_format, saved_path=os.path.dirname(file_path)
                    )
                    added_albums.add(album_id)

            except Exception as e:
                logger.error(f"{RED}[!] Error processing {file_path}: {e}{OFF}")

    except KeyboardInterrupt:
        logger.warning(f"\n{YELLOW}[!] Synchronization forcibly interrupted by user!{OFF}")
        logger.warning(f"{YELLOW}[!] Don't worry, all progress up to this point has been safely saved.{OFF}")

    logger.info(f"{GREEN}[+] Sync complete! Restored {added_tracks} tracks and {len(added_albums)} albums into the local database.{OFF}")