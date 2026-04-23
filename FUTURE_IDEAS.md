# qobuz-dl — Future Ideas

## `--karaoke` Mode

**Command:** `qobuz-dl dl --karaoke "https://play.qobuz.com/playlist/12345"`

**What it does:**
Downloads a playlist in "karaoke mode" — each track is packaged in its own subfolder containing both the audio file and an external `.lrc` (synced lyrics) file.

**Folder structure:**
```
My Playlist/
  01 - Song Title A/
    01 - Song Title A.flac
    01 - Song Title A.lrc
  02 - Song Title B/
    02 - Song Title B.flac
    02 - Song Title B.lrc
  03 - Song Title C/
    03 - Song Title C.flac     ← no synced lyrics found, no .lrc
```

**Behavior:**
- Overrides the default behavior (which only embeds lyrics into FLAC metadata)
- Saves an **external `.lrc` file** alongside the audio file for use with karaoke apps, car stereos, or players that don't support embedded lyrics
- Creates a **per-track subfolder** (named after the formatted track, e.g., `01 - Song Title`) to keep the audio + `.lrc` packaged together
- If no synced lyrics are found for a track, the track is still placed in its own subfolder (consistency) but without a `.lrc` file
- Works with both `dl` and `sync-playlist` commands

**Implementation notes:**
- Add `--karaoke` flag to `add_common_arg()` in `commands.py`
- Pass `karaoke=True` through to `Download.__init__()` and down to `lyrics_engine.fetch_and_inject()`
- In `lyrics_engine.py`, conditionally call `_save_lrc_file()` when karaoke mode is active
- In `downloader.py:download_track()`, when `is_playlist=True` and `karaoke=True`, create a per-track subfolder using the formatted track name before downloading
- Update `_prune_playlist()` and `sync_playlist.py` to handle per-track subfolder cleanup (`.lrc` deletion + empty dir removal)

**Use cases:**
- Karaoke nights with apps that read external `.lrc` files
- Offline lyric display on devices that don't support embedded FLAC tags
- Sharing lyrics files separately from audio
