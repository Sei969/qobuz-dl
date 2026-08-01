import os
import logging
from mutagen.flac import FLAC
from mutagen.id3 import ID3

from qobuz_dl.color import CYAN, GREEN, RED, YELLOW, OFF

logger = logging.getLogger(__name__)

def _scan_local_tracks(directory):
    local_tracks = {}
    untagged_files = []

    for root, _, files in os.walk(directory):
        for fname in files:
            if not fname.lower().endswith(('.flac', '.mp3')):
                continue

            fpath = os.path.join(root, fname)
            track_id = None

            try:
                if fpath.lower().endswith('.flac'):
                    audio = FLAC(fpath)
                    track_id_list = audio.get("QDL_TRACK_ID") or audio.get("QOBUZTRACKID") or [None]
                    track_id = track_id_list[0]
                else:
                    audio = ID3(fpath)
                    track_txxx = audio.get("TXXX:QDL_TRACK_ID") or audio.get("TXXX:qdl_track_id") or audio.get("TXXX:QOBUZTRACKID")
                    if track_txxx:
                        track_id = track_txxx.text[0]
            except Exception as e:
                logger.debug(f"Failed to read tags from {fpath}: {e}")

            if track_id:
                local_tracks[str(track_id)] = fpath
            else:
                untagged_files.append(fpath)

    return local_tracks, untagged_files

def _fetch_remote_tracks(client, playlist_id):
    all_items = []
    playlist_name = "Unknown Playlist"
    for chunk in client.get_plist_meta(playlist_id):
        if "name" in chunk and playlist_name == "Unknown Playlist":
            playlist_name = chunk.get("name")
        items = chunk.get("tracks", {}).get("items", [])
        all_items.extend(items)
    return playlist_name, all_items

def _sanitize_dirname(name):
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    return name.strip()

def _clean_empty_dirs(base_directory, exclude_dirs=None):
    exclude = set(exclude_dirs or [])
    exclude.add("_Playlists")

    for root, dirs, files in os.walk(base_directory, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                if d in exclude:
                    continue
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    rel = os.path.relpath(dir_path, base_directory)
                    logger.info(f"  {RED}[-] Removed empty dir: {rel}{OFF}")
            except OSError:
                pass

def sync_playlist(qobuz_dl, url, folder, auto_confirm=False):
    from qobuz_dl.utils import get_url_info, make_m3u

    try:
        url_type, playlist_id = get_url_info(url)
    except (AttributeError, IndexError):
        logger.error(f"{RED}Invalid URL: {url}{OFF}")
        return

    if url_type != "playlist":
        logger.error(
            f"{RED}URL is not a playlist (detected type: '{url_type}'). "
            f"Use a playlist URL like https://play.qobuz.com/playlist/12345{OFF}"
        )
        return

    logger.info(f"\n{YELLOW}━━━ PLAYLIST SYNC ━━━{OFF}")
    logger.info(f"{YELLOW}URL : {url}{OFF}")

    logger.info(f"{CYAN}[1/4] Fetching playlist from Qobuz...{OFF}")
    playlist_name, remote_items = _fetch_remote_tracks(qobuz_dl.client, playlist_id)
    remote_ids = {str(item["id"]): item for item in remote_items}
    logger.info(f"{CYAN}      Found {len(remote_ids)} tracks in the Qobuz playlist.{OFF}")

    if not remote_ids:
        logger.info(f"{YELLOW}The Qobuz playlist is empty. Nothing to sync.{OFF}")
        return

    safe_playlist_name = _sanitize_dirname(playlist_name)
    base_name = os.path.basename(os.path.normpath(folder))
    
    if base_name == safe_playlist_name:
        target_folder = folder
    else:
        target_folder = os.path.join(folder, safe_playlist_name)

    logger.info(f"{YELLOW}DIR : {target_folder}{OFF}\n")

    os.makedirs(target_folder, exist_ok=True)
    logger.info(f"{CYAN}[2/4] Scanning local folder...{OFF}")
    local_tracks, untagged = _scan_local_tracks(target_folder)
    logger.info(f"{CYAN}      Found {len(local_tracks)} tagged tracks locally.{OFF}")
    if untagged:
        logger.info(
            f"{YELLOW}      {len(untagged)} files have no QOBUZTRACKID tag and will be ignored.{OFF}"
        )

    local_id_set = set(local_tracks.keys())
    remote_id_set = set(remote_ids.keys())

    to_download_ids = remote_id_set - local_id_set
    to_delete_ids = local_id_set - remote_id_set
    already_synced = local_id_set & remote_id_set

    logger.info(f"\n{CYAN}[3/4] Sync summary:{OFF}")
    logger.info(f"  {GREEN}↓ To download : {len(to_download_ids)} tracks{OFF}")
    logger.info(f"  {RED}✕ To delete   : {len(to_delete_ids)} files{OFF}")
    logger.info(f"    Already synced: {len(already_synced)} tracks")

    if not to_download_ids and not to_delete_ids:
        logger.info(f"\n{GREEN}✓ Folder is already in sync with the playlist!{OFF}")
        
        if not getattr(qobuz_dl, 'no_m3u_for_playlists', False):
            make_m3u(target_folder, remote_items)
            logger.info(f"{CYAN}✓ Playlist .m3u file updated with latest track order.{OFF}")
        return

    if to_delete_ids:
        logger.info(f"\n{RED}Files to DELETE:{OFF}")
        for tid in sorted(to_delete_ids):
            logger.info(f"  {RED}✕ {os.path.basename(local_tracks[tid])}{OFF}")

    if to_download_ids:
        logger.info(f"\n{GREEN}Tracks to DOWNLOAD:{OFF}")
        for tid in sorted(to_download_ids):
            item = remote_ids[tid]
            album_artist = item.get("album", {}).get("artist", {}).get("name")
            performer_name = item.get("performer", {}).get("name", "Unknown")
            artist = performer_name if album_artist in [None, "Various Artists"] else album_artist
            title = item.get("title", "Unknown")
            logger.info(f"  {GREEN}↓ {artist} — {title}{OFF}")

    if not auto_confirm:
        try:
            answer = input(f"\n{YELLOW}Proceed with sync? [y/N]: {OFF}").strip().lower()
            if answer != 'y':
                logger.info(f"{YELLOW}Sync cancelled by user.{OFF}")
                return
        except (KeyboardInterrupt, EOFError):
            logger.info(f"\n{YELLOW}Sync cancelled.{OFF}")
            return

    logger.info(f"\n{CYAN}[4/4] Executing sync...{OFF}")

    deleted_count = 0
    for tid in to_delete_ids:
        fpath = local_tracks[tid]
        try:
            os.remove(fpath)
            deleted_count += 1
            logger.info(f"  {RED}[-] Deleted: {os.path.basename(fpath)}{OFF}")

            lrc_path = os.path.splitext(fpath)[0] + ".lrc"
            if os.path.isfile(lrc_path):
                os.remove(lrc_path)
                logger.info(f"  {RED}[-] Deleted: {os.path.basename(lrc_path)}{OFF}")
        except OSError as e:
            logger.error(f"  {RED}[!] Failed to delete {fpath}: {e}{OFF}")

    _clean_empty_dirs(target_folder, exclude_dirs={"_Playlists"})

    original_folder_format = qobuz_dl.folder_format
    original_multi_disc = qobuz_dl.settings.multiple_disc_one_dir
    qobuz_dl.folder_format = "."
    qobuz_dl.settings.multiple_disc_one_dir = True

    position_map = {}
    for idx, item in enumerate(remote_items, start=1):
        position_map[str(item["id"])] = idx

    downloaded_count = 0
    for tid in to_download_ids:
        playlist_idx = position_map.get(tid, 0)
        try:
            qobuz_dl.download_from_id(
                tid,
                album=False,
                alt_path=target_folder,
                is_playlist=True,
                playlist_index=playlist_idx,
            )
            downloaded_count += 1
        except Exception as e:
            logger.error(f"  {RED}[!] Failed to download track {tid}: {e}{OFF}")

    qobuz_dl.folder_format = original_folder_format
    qobuz_dl.settings.multiple_disc_one_dir = original_multi_disc

    if not getattr(qobuz_dl, 'no_m3u_for_playlists', False):
        make_m3u(target_folder, remote_items)

    logger.info(f"\n{GREEN}━━━ SYNC COMPLETE ━━━{OFF}")
    logger.info(f"  {GREEN}↓ Downloaded : {downloaded_count} tracks{OFF}")
    logger.info(f"  {RED}✕ Deleted    : {deleted_count} files{OFF}")
    logger.info(f"  {GREEN}✓ Total now  : {len(remote_ids)} tracks{OFF}\n")