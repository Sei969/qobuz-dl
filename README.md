# qobuz-dl Ultimate Edition
[![PyPI version](https://img.shields.io/pypi/v/qobuz-dl-ultimate.svg)](https://pypi.org/project/qobuz-dl-ultimate/) [![PyPI Downloads](https://static.pepy.tech/personalized-badge/qobuz-dl-ultimate?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/qobuz-dl-ultimate) ![Docker Image CI](https://github.com/Sei969/qobuz-dl/actions/workflows/docker.yml/badge.svg) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Sei969/qobuz-dl/blob/master/Qobuz_Ultimate_Colab.ipynb)

Search, explore, and download Lossless and Hi-Res music from [Qobuz](https://www.qobuz.com/).

**This is an enhanced, feature-rich fork of the original qobuz-dl project, designed for the ultimate audiophile experience. It includes a resilient download engine, deep customization for keeping your library perfectly organized, and extensive, native support for classical music metadata.**

## ✨ Features

### 🎧 Audiophile & Metadata Engine
* **Roon & DAP Optimized:** Metadata, cover art, and lyrics are meticulously formatted to ensure perfect out-of-the-box integration with Roon servers and Digital Audio Players.
* **Roon-Ready Synchronized Lyrics:** The engine intelligently formats and embeds timestamped `.lrc` data directly into the audio files (`[LYRICS]` Vorbis Comments), ensuring Roon natively displays scrolling, karaoke-style lyrics in its "Now Playing" view out-of-the-box.
* **Massive Tag Control:** Refactored tag engine supports highly detailed classical music metadata. Almost every single tag can be toggled on/off via CLI arguments.
* **Native Multi-Artist Tagging:** Automatically detects and splits main artists and featured guests. Unlike standard downloaders, it writes discrete multiple tags for FLAC files (Vorbis Comments) and standard null-separated strings for MP3s (ID3v2), ensuring flawless interpretation by high-end players like Roon, Plexamp, or Kodi without requiring external tools like MusicBrainz Picard.
* **Native ReplayGain Support:** Automatically extracts and embeds `REPLAYGAIN_TRACK_GAIN` and `REPLAYGAIN_TRACK_PEAK` tags directly from Qobuz's hidden API data. This ensures perfect, non-destructive volume leveling out-of-the-box for high-end digital audio players (DAPs) and audiophile servers like Roon.
* **Automatic Lyrics Engine & Retroactive Tagger:** Fetches and injects synchronized (`.lrc`) and unsynchronized lyrics using LRCLIB (with a Genius fallback API). Includes a standalone `lyrics` command to retroactively scan and inject missing lyrics into your existing local library without re-downloading the audio.
* **Enhanced Digital Booklets:** Automatically compiles a beautifully formatted `.txt` file with a complete tracklist, runtime, full credits, metadata, and reviews. Upon completion, the engine intelligently sweeps the folder, strips timestamps from `.lrc` files, and appends the pure text lyrics of the entire album directly into the booklet. Official PDF "Goodies" are also downloaded alongside it.

### 🚀 Resilient Download Engine
* **Bulletproof Queue:** Advanced track-level exception handling. If a single track is geo-blocked or missing from the servers (404 error), the engine gracefully skips it and seamlessly continues downloading the rest of your album or playlist without crashing.
* **Database Recovery & Sync:** Includes a specialized `--sync-db` engine to restore missing entries in your local database by scanning your existing music folders.
* **Bidirectional Playlist Sync (`sync-playlist`):** A powerful mirroring engine for dynamic playlists. Keep your local folders perfectly synced with online changes (downloading new tracks and cleanly deleting removed ones) without wasting bandwidth on unnecessary re-downloads.
* **Smart Reverse Lookup:** Automatically identifies legacy files by reading their **ISRC** or **UPC** tags and querying the Qobuz API to restore the correct IDs into the database.
* **Segmented Download & Remuxing:** Bypasses Akamai CDN throttling with a high-speed segmented download engine and automatic FFmpeg remuxing.
* **Multithreaded Downloading:** Concurrent track downloads for blazing-fast album fetching.
* **Clean Multithreading UI:** Intelligently switches to a clutter-free, static logging system displaying precise file sizes (MB) during concurrent downloads. This prevents terminal visual glitches and "cursor wars" with the Lyrics Engine, while preserving the classic animated progress bars for sequential (`--delay`) downloads.
* **Smart Quality Fallback:** Automatically downgrades to the next best available quality if the requested tier is restricted by the server, ensuring your download queue never crashes.
* **Authentication Bypass:** Log in securely using your browser's **Auth Token** if standard password authentication is blocked. Graciously handles Free/Studio accounts.
* **Limitless Playlists:** Overcomes Qobuz API restrictions by dynamically paginating chunk requests, allowing you to seamlessly queue and download massive playlists without the standard 50-track bottleneck.
* **Smart Resume (No Overwrites):** Intelligently detects existing files on your local drive and automatically skips them. If a massive discography download gets interrupted, it resumes instantly without wasting time or bandwidth re-downloading existing tracks.
* **Flawless `.m3u` Generation:** Automatically generates playlist files with correct relative folder paths. It uses smart API-driven ordering for dynamic playlists and a secure "Natural Sort" fallback for standard albums, guaranteeing the perfect playback sequence out-of-the-box in any media player.

### 📁 Advanced Formatting & Storage

Qobuz-DL Ultimate allows deep customization of your library structure using variables.

* **True Playlist Support (Native):** Seamlessly handles Qobuz and Last.fm playlists with a specialized logic designed for library organization (Fixes #257).
  * **Flat Folder Structure:** Automatically downloads all tracks into a single directory named after the playlist, preventing the creation of dozens of scattered album sub-folders.
  * **Position-Independent Naming:** Audio files are saved cleanly (e.g., `Artist - Title.flac`) without hardcoded numerical prefixes. This industry-standard approach ensures that if a playlist changes order online, your local files are recognized instantly, preventing massive duplicate re-downloads.
  * **Smart API-Driven `.m3u`:** Playback order is guaranteed by a dynamically generated `.m3u` file that perfectly mirrors the exact sequence dictated by the Qobuz servers, regardless of the physical files' names.
  * **Smart Cover Management:** Eliminates the "Cover Conflict" bug. The engine dynamically manages embedded artwork, ensuring each track gets its correct unique cover without leaving duplicate `cover.jpg` files in the folder.
* **Powerful Variables:** `folder_format` and `track_format` now support dozens of new variables (e.g., `{isrc}`, `{barcode}`, `{label}`, `{track_composer}`).
* **Release Type (`{release_type}`):** Automatically identifies the publication category from Qobuz APIs (e.g., `Album`, `EP`, `Single`), allowing you to dynamically route downloads into subdirectories or use it as a naming prefix without enforcing a fixed structure.
  * *Folder Example (Subdirectory):* `folder_format = {release_type}/{album_artist} - {album_title}` ➔ `Album/Daft Punk - Discovery`
  * *Folder Example (Prefix):* `folder_format = {release_type} - {album_artist} - {album_title}` ➔ `Single - Gorillaz - Silent Running`
* **Explicit Tag (`{explicit}` or `{ExplicitFlag}`):** Automatically adds an `[E]` tag if the track or album is marked with a parental advisory warning on Qobuz. If the content is clean, the variable remains empty without leaving unwanted trailing spaces. **You can apply this permanently by adding the variables to your `config.ini` file, or temporarily via CLI using the `-ff` and `-tf` flags.**
  * *Folder Example:* `folder_format = {artist} - {album} {ExplicitFlag}` ➔ `Eminem - The Eminem Show [E]`
  * *Track Example:* `track_format = {track_number} - {track_title} {ExplicitFlag}` ➔ `02 - Without Me [E].flac`
* **Album Version Tag (`{version_tag}`):** Automatically appends the album version (e.g., Live, Remastered, Deluxe Edition) to your folder or track name. If the release is a standard edition, the variable remains completely empty, preventing unwanted trailing spaces or dashes.
  * *Folder Example (Standard):* `folder_format = {album_artist} - {album_title}{version_tag}` ➔ `The Sunset Violent`
  * *Folder Example (Special Edition):* `folder_format = {album_artist} - {album_title}{version_tag}` ➔ `The Sunset Violent - Live in Heidelberg`
* **Multi-Disc Routing:** Store multiple disc releases in one single directory or split them using customizable prefixes (e.g., `CD 01`).
* **Universal Playlist Generation:** `.m3u` files are strictly UTF-8 encoded, ensuring 100% crash-free generation even with complex Unicode or Japanese characters (Fixes #304).

### ❤️ Native Favorites Sync & Interactive Menu
Seamlessly bridge your mobile listening habits with your local offline library. Instead of manually copying URLs, launch the Interactive Mode (`fun`) to securely access your personal Qobuz account and browse your **Favorite Albums, Tracks, Artists, and Playlists** directly from the terminal.
* **Zero-Typing Workflow:** Fetch your private library with a single click without ever leaving the terminal.
* **Massive Batch Downloading:** Use the `Spacebar` to multi-select dozens of your favorite releases from the clean, minimalist UI and queue them all up for download in seconds.

### 🌉 Last.fm Smart Integration & Interactive Mode
Seamlessly bridge your Last.fm world with Qobuz. Download your personalized playlists and "Loved Tracks" with ease. 
To prevent downloading incorrect songs, this fork utilizes a mathematical **Fuzzy Matching Algorithm**:
* **Auto-Accept (> 75%):** Perfect matches are automatically queued.
* **Auto-Skip (< 60%):** Completely wrong tracks are automatically skipped.
* **Interactive Selection (60% - 74%):** For borderline matches, the engine pauses and activates an interactive prompt allowing you to manually approve or reject the track (`[y/n]`).

### 📡 MusicButler RSS Radar (Automated Favorites Sync)
Never miss a new release from your tracked artists. The new `radar` command seamlessly integrates with your private **MusicButler** RSS feed to automate your discovery workflow.
* **Smart Feed Parsing:** Automatically fetches and parses your private RSS/Atom feed to find the latest releases from the artists you follow.
* **Fuzzy Qobuz Matching:** Queries the Qobuz database to find the exact high-resolution matches for your daily new releases.
* **Interactive Checkbox UI:** Presents a clean, interactive terminal menu where you can multi-select (`Spacebar`) the fresh releases and instantly inject them into your Qobuz Favorites (`Enter`), ready to be downloaded later via the `fun` mode.

### 🛡️ Fail-Safe Folder Management & Smart Resume
Say goodbye to messy libraries and corrupted downloads. The downloader now features a dynamic 3-stage folder state system to keep your music library perfectly organized:
* **`[IN PROGRESS]`**: Folders are marked while the download is actively running.
* **`[INCOMPLETE]`**: If you abort the process (graceful `CTRL+C` handling) or if some tracks are skipped (e.g., geo-blocked or unavailable), the folder is safely marked as incomplete. 
* **Clean State**: Only when an album is downloaded with **100% success** will the folder be renamed to its final, clean state (e.g., `Artist - Album`).

*Note: The engine is smart enough to seamlessly resume downloads directly into `[INCOMPLETE]` or `[IN PROGRESS]` folders on your next run!*

## 📥 Installation & Setup

> ⚠️ **Requirement:** You need an **active subscription** to Qobuz.

### Option A: 📦 PyPI Package (Recommended for all platforms)
The easiest and official way to install the Ultimate Edition. Open your terminal and run:
```bash
pip install qobuz-dl-ultimate
```
*Once installed, you can launch the program from any folder on your computer by simply typing `qobuz-dl` or `qdl`.*

### Option B: Pre-built Binaries (Windows x64)
The easiest way to run the program on Windows without installing Python.
👉 **[Download the latest ZIP here](https://github.com/Sei969/qobuz-dl/releases/latest)**
* **Portable:** No installation required.
* **Important:** Just extract the `.zip` and ensure `ffmpeg.exe` and `qobuz-dl-ultimate.exe` are in the same folder.

### Option C: Python Source (Advanced)
Clone this repository and install the required dependencies:
```bash
git clone [https://github.com/Sei969/qobuz-dl.git](https://github.com/Sei969/qobuz-dl.git)
cd qobuz-dl
pip3 install -r requirements.txt
```
*Run the program using:* `python -m qobuz_dl`

### Option D: 🐳 Docker Usage (NAS & Home Servers)
The Ultimate Edition is fully containerized and includes all dependencies (Python, FFmpeg). This is the recommended installation method for Synology, QNAP, Unraid, and headless servers.
```bash
# Pull the latest official image
docker pull ghcr.io/sei969/qobuz-dl:latest

# Example: Run a download and map it to your NAS music folder
docker run -it --rm \
  -v /path/to/your/nas/music:/app/QobuzDownloads \
  ghcr.io/sei969/qobuz-dl:latest dl "[https://play.qobuz.com/album/](https://play.qobuz.com/album/)..."
```

### Option E: ☁️ Google Colab (Cloud & Google Drive)
The fastest way to download directly to your Google Drive at Gigabit speeds, bypassing local network limitations. Zero installation required.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Sei969/qobuz-dl/blob/master/Qobuz_Ultimate_Colab.ipynb)

* **Zero Setup:** Runs entirely in your browser (works seamlessly on smartphones and tablets too).
* **Usage:** Click the badge above, run the setup cells to mount your Google Drive, paste your Qobuz Auth Token, and start downloading directly to the cloud.

### ⚙️ Configuration & Custom Paths
If you want to set a custom download folder, you can edit your `config.ini` file and use the `directory` key. Absolute paths and the `~` operator (for macOS/Linux) are fully supported!
```ini
[qobuz]
directory = ~/Music/Qobuz_Lossless
```
*(Note: If you are upgrading from an older version, the legacy `default_folder` key is still fully supported for backward compatibility.)*

### 🔑 How to get your Auth Token
Since Qobuz blocked direct password logins for third-party applications, you need to provide your browser's Auth Token during the initial configuration. Here is how to easily find it:
1. Open the [Qobuz Web Player](https://play.qobuz.com) in your browser and log in.
2. Press `F12` to open the Developer Tools.
3. Go to the **Application** tab (Chrome/Edge) or **Storage** tab (Firefox).
4. In the left sidebar, expand **Local Storage** and click on `https://play.qobuz.com`.
5. In the list of keys, find **`localuser`**.
6. At the bottom of the panel (or by expanding the JSON value), look for the **`token`** string.
7. Copy that alphanumeric string and paste it into the `qobuz-dl` terminal wizard!

## 💻 Usage & Quick Examples

```text
[Global Commands & Database Management]
usage: python -m qobuz_dl [-h] [-r] [-p] [--sync-db [PATH]] [-sc] {interactive,i,fun,dl,lucky,lyrics,radar,sync-playlist,sp} ...

[Download Usage]
usage: python -m qobuz_dl dl [-h] [-d PATH] [-q int] [--albums-only] [--no-m3u] [--no-fallback] [--no-db] 
                             [-ff PATTERN] [-tf PATTERN] [-s] [-e] [--no-cover]
                             [--embedded-art-size {50,100,150,300,600,max,org}] 
                             [--saved-art-size {50,100,150,300,600,max,org}] 
                             [--multiple-disc-prefix PREFIX] [--multiple-disc-one-dir] 
                             [--no-lyrics] [--native-lang] [--no-credits] [--delay SECONDS]
                             [--no-album-artist-tag] [--no-track-composer-tag] ... 
                             SOURCE [SOURCE ...]
```

**MusicButler Radar Mode:**
*(Tip: Run it once to save your RSS link, then run it daily to catch new releases and securely add them to your Qobuz favorites!)*
```bash
python -m qobuz_dl radar
```

**Bidirectional Playlist Sync:**
*(Tip: Add `-y` to bypass confirmation prompts, and `--no-db` to force the engine to rely strictly on the physical files present in the folder).*
```bash
python -m qobuz_dl sp "URL" "C:\Path\To\Local\Playlist\Folder"
```
                            
**Basic Album/Playlist Download:**
```bash
python -m qobuz_dl dl [https://play.qobuz.com/album/qxjbxh1dc3xyb](https://play.qobuz.com/album/qxjbxh1dc3xyb)
```

**Mass/Batch Downloading:**
Do you have a massive list of releases to download? Create a standard text file (e.g., `list.txt`), paste all your Qobuz URLs inside (one per line), and pass it to the engine. It will automatically read the file and download your entire queue!
```bash
python -m qobuz_dl dl list.txt
```

**Safe Download (Anti-Ban):**
Disables multithreading to simulate human behavior during massive download sessions.
```bash
python -m qobuz_dl dl <URL> --delay 1
```

**Advanced Discography Routing:**
Save multiple discs of a release in one single folder instead of splitting them.
```bash
python -m qobuz_dl dl [https://play.qobuz.com/artist/2038380](https://play.qobuz.com/artist/2038380) --multiple-disc-one-dir
```

**Interactive Last.fm Mode (Fun Mode):**
*(Tip: In interactive mode, use `Space` to multi-select several albums to download at once!)*
```bash
python -m qobuz_dl fun -l 10
```

### 🗄️ Database & Library Management
The Ultimate Edition includes powerful local library managers to keep track of your downloads, prevent duplicates, and retroactively fix your metadata.

* **Smart Library Sync (`--sync-db`):**
  Already have a local library of downloaded FLACs? You don't need to start from scratch. Run this command to perform a *Reverse Lookup* on your download directory. The engine will scan your existing files and automatically inject them into the local database to prevent duplicate downloads in the future.
  ```bash
  python -m qobuz_dl --sync-db
  ```
  *(Note: You can also specify a custom path to scan, e.g., `--sync-db "/path/to/your/music"`)*

* **Dynamic Playlist Sync (`sync-playlist` / `sp`):**
  Playlists are living entities. Instead of re-downloading a playlist every time the author adds a new song, point this command to your existing folder. It will scan the local tags, interrogate the Qobuz API, and calculate the exact delta: downloading only the missing tracks, cleanly deleting removed ones (alongside their `.lrc` companions), and regenerating the `.m3u` order.
  ```bash
  python -m qobuz_dl sp "PLAYLIST_URL" "/path/to/your/local/folder"
  ```

* **Retroactive Lyrics Tagger (`lyrics`):**
  Do you have an existing local music library that lacks synced lyrics? The new `lyrics` command acts as a standalone metadata engine. It recursively scans any local directory, detects FLAC/MP3 files missing lyrics, and intelligently injects them into the audio files using LRCLIB (and Genius API) without re-downloading any music.
  ```bash
  python -m qobuz_dl lyrics "/path/to/your/local/music/folder"
  ```

* **Purge Database (`-p`, `--purge`):**
  If you ever need to start fresh, clear your download history, or fix a corrupted state, you can instantly wipe the local database with a single command.
  ```bash
  python -m qobuz_dl --purge
  ```

### 🛠️ Key Formatting Variables

You can customize your `config.ini` or use the CLI flags `-ff` (Folder Format) and `-tf` (Track Format) with these powerful variables:

* **Folder Pattern (`-ff`):** Supports dynamic routing with `{release_type}`, `{album_artist}`, `{year}`, `{label}`, and `{barcode}`.
* **Track Pattern (`-tf`):** Customize filenames using `{track_number}`, `{track_title}`, `{isrc}`, and `{track_composer}`.
* **Explicit Flag:** Use `{ExplicitFlag}` or `{explicit}` within your patterns to automatically mark parental advisory content.

*Detailed variable usage and examples can be found in the [Advanced Formatting & Storage](#-advanced-formatting--storage) section.*

## 🏆 Credits
* **[vitiko98](https://github.com/vitiko98/qobuz-dl)**: Creator of the original project.
* **[xwell](https://github.com/xwell/qobuz-dl)**: For the massive tag refactoring and "Goodies" integration.
* **[catap](https://github.com/catap)**: For the segmented download patch.
* **Sorrow446 & DashLt**: `qobuz-dl` is inspired by the discontinued Qo-DL-Reborn. This tool uses the core API module `qopy`, originally written by them.

## ⚠️ Disclaimer
* This tool was written for educational purposes.
* `qobuz-dl` is not affiliated with Qobuz.