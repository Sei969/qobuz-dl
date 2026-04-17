# qobuz-dl Ultimate Edition
![Docker Image CI](https://github.com/Sei969/qobuz-dl/actions/workflows/docker.yml/badge.svg)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Sei969/qobuz-dl/blob/master/Qobuz_Ultimate_Colab.ipynb)

Search, explore, and download Lossless and Hi-Res music from [Qobuz](https://www.qobuz.com/).

**This is an enhanced, feature-rich fork of the original qobuz-dl project, designed for the ultimate audiophile experience. It includes a resilient download engine, deep customization for keeping your library perfectly organized, and extensive, native support for classical music metadata.**

## ✨ Features

### 🎧 Audiophile & Metadata Engine
* **Roon & DAP Optimized:** Metadata, cover art, and lyrics are meticulously formatted to ensure perfect out-of-the-box integration with Roon servers and Digital Audio Players.
* **Massive Tag Control:** Refactored tag engine supports highly detailed classical music metadata. Almost every single tag can be toggled on/off via CLI arguments.
* **Automatic Lyrics Engine:** Fetches and injects synchronized (`.lrc`) and unsynchronized lyrics using LRCLIB (with a Genius fallback API).
* **Digital Booklets & Goodies:** Automatically compiles a `.txt` file with a complete tracklist, full credits, metadata, and reviews, while simultaneously downloading official PDF "Goodies" (Booklets).

### 🚀 Resilient Download Engine
* **Database Recovery & Sync:** Includes a specialized `--sync-db` engine to restore missing entries in your local database by scanning your existing music folders.
* **Smart Reverse Lookup:** Automatically identifies legacy files by reading their **ISRC** or **UPC** tags and querying the Qobuz API to restore the correct IDs into the database.
* **Segmented Download & Remuxing:** Bypasses Akamai CDN throttling with a high-speed segmented download engine and automatic FFmpeg remuxing.
* **Multithreaded Downloading:** Concurrent track downloads for blazing-fast album fetching.
* **Clean Multithreading UI:** Intelligently switches to a clutter-free, static logging system displaying precise file sizes (MB) during concurrent downloads. This prevents terminal visual glitches and "cursor wars" with the Lyrics Engine, while preserving the classic animated progress bars for sequential (`--delay`) downloads.
* **Smart Quality Fallback:** Automatically downgrades to the next best available quality if the requested tier is restricted by the server, ensuring your download queue never crashes.
* **Authentication Bypass:** Log in securely using your browser's `user_auth_token` if standard password authentication is blocked. Graciously handles Free/Studio accounts.

### 📁 Advanced Formatting & Storage

Qobuz-DL Ultimate allows deep customization of your library structure using variables.

* **True Playlist Support (Native):** Seamlessly handles Qobuz and Last.fm playlists with a specialized logic designed for library organization (Fixes #257).
  * **Flat Folder Structure:** Automatically downloads all tracks into a single directory named after the playlist, preventing the creation of dozens of scattered album sub-folders.
  * **Sequential Track Numbering:** Overrides original album track numbers with the playlist's actual order (`01`, `02`, `03`...), ensuring a perfect chronological playback experience.
  * **Smart Cover Management:** Eliminates the "Cover Conflict" bug. The engine now dynamically manages embedded artwork, ensuring each track gets its correct unique cover without leaving duplicate `cover.jpg` files in the folder.
* **Powerful Variables:** `folder_format` and `track_format` now support dozens of new variables (e.g., `{isrc}`, `{barcode}`, `{label}`, `{track_composer}`).
* **Release Type (`{release_type}`):** Automatically identifies the publication category from Qobuz APIs (e.g., `Album`, `EP`, `Single`), allowing you to dynamically route downloads into subdirectories or use it as a naming prefix without enforcing a fixed structure.
  * *Folder Example (Subdirectory):* `folder_format = {release_type}/{album_artist} - {album_title}` ➔ `Album/Daft Punk - Discovery`
  * *Folder Example (Prefix):* `folder_format = {release_type} - {album_artist} - {album_title}` ➔ `Single - Gorillaz - Silent Running`
* **Explicit Tag (`{explicit}` or `{ExplicitFlag}`):** Automatically adds an `[E]` tag if the track or album is marked with a parental advisory warning on Qobuz. If the content is clean, the variable remains empty without leaving unwanted trailing spaces. **You can apply this permanently by adding the variables to your `config.ini` file, or temporarily via CLI using the `-ff` and `-tf` flags.**
  * *Folder Example:* `folder_format = {artist} - {album} {ExplicitFlag}` ➔ `Eminem - The Eminem Show [E]`
  * *Track Example:* `track_format = {track_number} - {tracktitle} {ExplicitFlag}` ➔ `02 - Without Me [E].flac`
* **Multi-Disc Routing:** Store multiple disc releases in one single directory or split them using customizable prefixes (e.g., `CD 01`).
* **Universal Playlist Generation:** `.m3u` files are strictly UTF-8 encoded, ensuring 100% crash-free generation even with complex Unicode or Japanese characters (Fixes #304).

### 🌉 Last.fm Smart Integration & Interactive Mode
Seamlessly bridge your Last.fm world with Qobuz. Download your personalized playlists and "Loved Tracks" with ease. 
To prevent downloading incorrect songs, this fork utilizes a mathematical **Fuzzy Matching Algorithm**:
* **Auto-Accept (> 75%):** Perfect matches are automatically queued.
* **Auto-Skip (< 60%):** Completely wrong tracks are automatically skipped.
* **Interactive Selection (60% - 74%):** For borderline matches, the engine pauses and activates an interactive prompt allowing you to manually approve or reject the track (`[y/n]`).

## 📥 Installation & Setup

> ⚠️ **Requirement:** You need an **active subscription** to Qobuz.

### Option A: Pre-built Binaries (Windows x64)
The easiest way to run the program on Windows without installing Python.
👉 **[Download the latest ZIP here](https://github.com/Sei969/qobuz-dl/releases/latest)**
* **Portable:** No installation required.
* **Important:** Just extract the `.zip` and ensure `ffmpeg.exe` and `qobuz-dl-ultimate.exe` are in the same folder.

### Option B: Python Source (Linux, macOS, Windows)
Clone this repository and install the required dependencies:
```bash
git clone [https://github.com/Sei969/qobuz-dl.git](https://github.com/Sei969/qobuz-dl.git)
cd qobuz-dl
pip3 install -r requirements.txt
```
*Run the program using:* `python -m qobuz_dl`

### Option C: 🐳 Docker Usage (NAS & Home Servers)
The Ultimate Edition is fully containerized and includes all dependencies (Python, FFmpeg). This is the recommended installation method for Synology, QNAP, Unraid, and headless servers.

```bash
# Pull the latest official image
docker pull ghcr.io/sei969/qobuz-dl:latest

# Example: Run a download and map it to your NAS music folder
docker run -it --rm \
  -v /path/to/your/nas/music:/app/QobuzDownloads \
  ghcr.io/sei969/qobuz-dl:latest dl "[https://play.qobuz.com/album/](https://play.qobuz.com/album/)..."
  ```
## 💻 Usage & Quick Examples

```text
[Global Commands & Database Management]
usage: python -m qobuz_dl [-h] [-r] [-p] [--sync-db [PATH]] [-sc] {interactive,i,fun,dl,lucky} ...

[Download Usage]
usage: python -m qobuz_dl dl [-h] [-d PATH] [-q int] [--albums-only] [--no-m3u] [--no-fallback] [--no-db] 
                             [-ff PATTERN] [-tf PATTERN] [-s] [-e] [--no-cover]
                             [--embedded-art-size {50,100,150,300,600,max,org}] 
                             [--saved-art-size {50,100,150,300,600,max,org}] 
                             [--multiple-disc-prefix PREFIX] [--multiple-disc-one-dir] 
                             [--no-lyrics] [--native-lang] [--no-credits] [--delay SECONDS]
                             [--no-album-artist-tag] [--no-track-composer-tag] ... 
                             SOURCE [SOURCE ...]
							 
**Basic Album/Playlist Download:**
```bash
python -m qobuz_dl dl [https://play.qobuz.com/album/qxjbxh1dc3xyb](https://play.qobuz.com/album/qxjbxh1dc3xyb)
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

**Database Sync:**
Scans the specified directory to restore missing Qobuz IDs into your local database. (Uses default download folder if no path is provided).
```bash
python -m qobuz_dl dl --sync-db "C:\My Music"
```

**Interactive Last.fm Mode (Fun Mode):**
*(Tip: In interactive mode, use `Space` to multi-select several albums to download at once!)*
```bash
python -m qobuz_dl fun -l 10
```							 

### 🛠️ Key Formatting Variables

You can customize your `config.ini` or use the CLI flags `-ff` (Folder Format) and `-tf` (Track Format) with these powerful variables:

* **Database Sync (`--sync-db [PATH]`):** Scans the specified directory to restore missing Qobuz IDs into your local database. If no path is provided, it uses the default download folder.
* **Folder Pattern (`-ff`):** Supports dynamic routing with `{release_type}`, `{album_artist}`, `{year}`, `{label}`, and `{barcode}`.
* **Track Pattern (`-tf`):** Customize filenames using `{track_number}`, `{track_title}`, `{isrc}`, and `{track_composer}`.
* **Explicit Flag:** Use `{ExplicitFlag}` or `{explicit}` within your patterns to automatically mark parental advisory content.

*Detailed variable usage and examples can be found in the [Advanced Formatting & Storage](#-advanced-formatting--storage) section.*

## 🏆 Credits
* **[vitiko98](https://github.com/vitiko98/qobuz-dl)**: Creator of the original project.
* **[xwell](https://github.com/xwell/qobuz-dl)**: For the massive tag refactoring and "Goodies" integration.
* **[catap](https://github.com/catap)**: For the segmented download patch.

## ⚠️ Disclaimer
* This tool was written for educational purposes.
* `qobuz-dl` is not affiliated with Qobuz.