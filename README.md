# qobuz-dl Ultimate
Search, explore, and download Lossless and Hi-Res music from [Qobuz](https://www.qobuz.com/).
**This is an enhanced, feature-rich fork of the original qobuz-dl project, designed for the ultimate audiophile experience. It includes extensive, native support for classical music metadata to keep your library perfectly organized.**

## Features & Ultimate Additions

## Features & Ultimate Additions

* **[NEW] Automatic Lyrics Engine:** Fetches and injects synchronized (`.lrc`) and unsynchronized lyrics using LRCLIB (with a Genius fallback API).
* **[NEW] Digital Booklet Generation:** Automatically compiles a `.txt` file with a complete tracklist (including track durations), full credits, metadata, and album reviews for every download.
* **[NEW] Segmented Download & Remuxing:** Bypasses Akamai CDN throttling with a high-speed, multithreaded segmented download engine and automatic FFmpeg remuxing.
* **[NEW] Smart Quality Fallback:** Automatically downgrades to the next best available quality if the requested tier is restricted by the server, ensuring your download queue never crashes.
* **[NEW] Token Authentication:** Log in securely using your browser's `user_auth_token` if standard password authentication is blocked by Qobuz.
* **[NEW] Regional Bypass:** Forces English language for metadata, reviews, and digital booklets regardless of your account's native region.
* **[NEW] International & Clean Outputs:** Console logs and outputs have been fully translated to English and modernized for a cleaner terminal experience.
* Download FLAC and MP3 files from Qobuz
* Explore and download music directly from your terminal with **interactive** or **lucky** mode
* Download albums, tracks, artists, playlists, and labels with **download** mode
* Download music from last.fm playlists
* Queue support and **multiselect** on **interactive** mode
* Effective duplicate handling with own portable database
* Support for albums with multiple discs and M3U playlists
* Downloads URLs from text files
* Extended tags and more...

### 🛠️ Upstream Pull Requests & Issues Resolved
* **Interactive Mode Restored & Enhanced (PR #179):** Fixed the critical crash caused by the deprecated `options_map_func` in the `pick` library. The interactive menu is fully working again and now supports **multiselect** (press `Space` to queue multiple releases at once!). The command has also been renamed to `interactive` (or `-i`), while keeping `fun` as an alias for retro-compatibility.
* **Free Account Handling (Issue #261):** Cleaned up the `IneligibleError` handling. The script now gracefully bypasses streamable checks for free accounts, defaulting purchased items to Studio quality without crashing.

## Getting started

> You'll need an **active subscription** to Qobuz.

#### Installation
Clone this repository and install the required dependencies:
```bash
git clone https://github.com/Sei969/qobuz-dl.git
cd qobuz-dl
pip3 install -r requirements.txt
```
*(Windows users may also need to run `pip3 install windows-curses` for interactive mode).*

#### Run qobuz-dl and enter your credentials
To ensure maximum compatibility and avoid namespace conflicts, it is recommended to run the script as a Python module from the root folder:

```bash
python -m qobuz_dl
```

> If something fails, run `python -m qobuz_dl -r` to reset your config file and launch the interactive setup wizard.

## Examples

### Download mode
Download URL in 24B<96khz quality:
```bash
python -m qobuz_dl dl https://play.qobuz.com/album/qxjbxh1dc3xyb -q 7
```

Download multiple URLs to a custom directory:
```bash
python -m qobuz_dl dl https://play.qobuz.com/artist/2038380 https://play.qobuz.com/album/ip8qjy1m6dakc -d "Some pop from 2020"
```

### [NEW] Ultimate Features Examples
Download an album but **disable** the automatic lyrics fetching for this session:
```bash
python -m qobuz_dl dl https://play.qobuz.com/album/qxjbxh1dc3xyb --no-lyrics
```

Download an album and **disable** the generation of the "Digital Booklet.txt (Credits & Review)" file:
```bash
python -m qobuz_dl dl https://play.qobuz.com/album/qxjbxh1dc3xyb --no-credits
```

Download metadata, reviews, and credits in your account's **native language** (disabling the English regional bypass):
```bash
python -m qobuz_dl dl https://play.qobuz.com/album/qxjbxh1dc3xyb --native-lang
```

Combine all exclusion flags for a pure, bare-bones audio download:
```bash
python -m qobuz_dl dl https://play.qobuz.com/album/qxjbxh1dc3xyb --no-lyrics --no-credits --native-lang
```

#### Last.fm playlists
Download a last.fm playlist in the maximum quality:
```bash
python -m qobuz_dl dl https://www.last.fm/user/vitiko98/playlists/11887574 -q 27
```

Run `python -m qobuz_dl dl --help` for more info.

### Interactive mode
Run interactive mode with a limit of 10 results:
```bash
python -m qobuz_dl fun -l 10
```

### Lucky mode
Download the first 3 track results in 320 quality:
```bash
python -m qobuz_dl lucky eric dolphy remastered --type track -n 3 -q 5
```

## Usage
```text
usage: python -m qobuz_dl [-h] [-r] [-p] [-sc] {fun,dl,lucky} ...

The ultimate Qobuz music downloader.
See usage examples on https://github.com/Sei969/qobuz-dl

optional arguments:
  -h, --help           show this help message and exit
  -r, --reset          create/reset config file
  -p, --purge          purge/delete downloaded-IDs database
  -sc, --show-config   show configuration

commands:
  run python -m qobuz_dl <command> --help for more info
  (e.g. python -m qobuz_dl dl --help)

  {fun,dl,lucky}
    fun                interactive mode
    dl                 input mode
    lucky              lucky mode
```

### Download Mode Usage
```text
usage: python -m qobuz_dl dl [-h] [-d PATH] [-q int] [--albums-only] [--no-m3u]
                             [--no-fallback] [-e] [--og-cover] [--no-cover]
                             [--no-db] [-ff PATTERN] [-tf PATTERN] [-s]
                             [--no-lyrics] [--native-lang] [--no-credits]
                             SOURCE [SOURCE ...]

Download by album/track/artist/label/playlist/last.fm-playlist URL.

positional arguments:
  SOURCE                one or more URLs (space separated) or a text file

optional arguments:
  -h, --help            show this help message and exit
  -d PATH, --directory PATH
                        directory for downloads (default: "Qobuz Downloads")
  -q int, --quality int
                        audio "quality" (5, 6, 7, 27)
                        [320, LOSSLESS, 24B<=96KHZ, 24B>96KHZ] (default: 27)
  --albums-only         don't download singles, EPs and VA releases
  --no-m3u              don't create .m3u files when downloading playlists
  --no-fallback         disable quality fallback (skip releases not available in set quality)
  -e, --embed-art       embed cover art into files
  --og-cover            download cover art in its original quality (bigger file)
  --no-cover            don't download cover art
  --no-db               don't call the database
  -ff PATTERN, --folder-format PATTERN
                        pattern for formatting folder names
  -tf PATTERN, --track-format PATTERN
                        pattern for formatting track names
  -s, --smart-discography
                        Try to filter out spam-like albums when requesting an artist's discography...

ultimate exclusive features:
  --no-lyrics           disable automatic lyrics fetching and injection for this session
  --native-lang         do not force English; download metadata in the account's native language
  --no-credits          disable the generation of the Digital Booklet.txt (Credits & Review) file
```
## Credits
* This "Ultimate Edition" is a fork of the original `qobuz-dl` project created by **[vitiko98](https://github.com/vitiko98/qobuz-dl)**. A huge thanks to him and all the original contributors for laying the foundation of this amazing tool.
* A special thanks to **[catap](https://github.com/catap)** for the segmented download patch, which brilliantly bypasses the Akamai CDN throttling.

## A note about Qo-DL
`qobuz-dl` is inspired in the discontinued Qo-DL-Reborn. This tool uses two modules from Qo-DL: `qopy` and `spoofer`, both written by Sorrow446 and DashLt.

## Disclaimer
* This tool was written for educational purposes. I will not be responsible if you use this program in bad faith. By using it, you are accepting the [Qobuz API Terms of Use](https://static.qobuz.com/apps/api/QobuzAPI-TermsofUse.pdf).
* `qobuz-dl` is not affiliated with Qobuz.
