# qobuz-dl Ultimate Edition
Search, explore, and download Lossless and Hi-Res music from [Qobuz](https://www.qobuz.com/).

**This is an enhanced, feature-rich fork of the original qobuz-dl project, designed for the ultimate audiophile experience. It includes a resilient download engine, deep customization for keeping your library perfectly organized, and extensive, native support for classical music metadata.**

## ✨ Features

### 🎧 Audiophile & Metadata Engine
* **Roon & DAP Optimized:** Metadata, cover art, and lyrics are meticulously formatted to ensure perfect out-of-the-box integration with Roon servers and Digital Audio Players.
* **Massive Tag Control:** Refactored tag engine supports highly detailed classical music metadata. Almost every single tag can be toggled on/off via CLI arguments.
* **Automatic Lyrics Engine:** Fetches and injects synchronized (`.lrc`) and unsynchronized lyrics using LRCLIB (with a Genius fallback API).
* **Digital Booklets & Goodies:** Automatically compiles a `.txt` file with a complete tracklist, full credits, metadata, and reviews, while simultaneously downloading official PDF "Goodies" (Booklets).

### 🚀 Resilient Download Engine
* **Segmented Download & Remuxing:** Bypasses Akamai CDN throttling with a high-speed segmented download engine and automatic FFmpeg remuxing.
* **Multithreaded Downloading:** Concurrent track downloads for blazing-fast album fetching.
* **Clean Multithreading UI:** Intelligently switches to a clutter-free, static logging system displaying precise file sizes (MB) during concurrent downloads. This prevents terminal visual glitches and "cursor wars" with the Lyrics Engine, while preserving the classic animated progress bars for sequential (`--delay`) downloads.
* **Smart Quality Fallback:** Automatically downgrades to the next best available quality if the requested tier is restricted by the server, ensuring your download queue never crashes.
* **Authentication Bypass:** Log in securely using your browser's `user_auth_token` if standard password authentication is blocked. Graciously handles Free/Studio accounts.

### 📁 Advanced Formatting & Storage
* **True Playlist Support (Native):** Seamlessly handles Qobuz and Last.fm playlists with a specialized logic designed for library organization (Fixes #257).
  * **Flat Folder Structure:** Automatically downloads all tracks into a single directory named after the playlist, preventing the creation of dozens of scattered album sub-folders.
  * **Sequential Track Numbering:** Overrides original album track numbers with the playlist's actual order (`01`, `02`, `03`...), ensuring a perfect chronological playback experience.
  * **Smart Cover Management:** Eliminates the "Cover Conflict" bug. The engine now dynamically manages embedded artwork, ensuring each track gets its correct unique cover without leaving duplicate `cover.jpg` files in the folder.
* **Powerful Variables:** `folder_format` and `track_format` now support dozens of new variables (e.g., `{isrc}`, `{barcode}`, `{label}`, `{track_composer}`).
* **Explicit Tag (`{explicit}` or `{ExplicitFlag}`):** Adds an `[E]` tag for parental advisory content. You can apply this permanently in your `config.ini` or via CLI.
* **Multi-Disc Routing:** Store multiple disc releases in one single directory or split them using customizable prefixes (e.g., `CD 01`).
* **Universal Playlist Generation:** `.m3u` files are strictly UTF-8 encoded, ensuring 100% crash-free generation even with complex Unicode or Japanese characters (Fixes #304).

### 🌉 Last.fm Smart Integration
Seamlessly bridge your Last.fm world with Qobuz. Download your personalized playlists and "Loved Tracks" with ease. Enjoy seamless downloading of massive playlists with zero crashes at the finish line, keeping all your album covers and metadata perfectly intact.

#### Smart Track Matching & Interactive Mode
Track names often differ slightly between platforms. To prevent downloading incorrect songs, this fork utilizes a mathematical **Fuzzy Matching Algorithm**:

* **Auto-Accept (> 75% similarity):** Perfect or near-perfect matches are automatically queued and downloaded.
* **Auto-Skip (< 60% similarity):** Completely wrong tracks are automatically skipped, keeping your hard drive clean.
* **Interactive Selection (60% - 74% similarity):** For borderline matches, the engine pauses and activates an interactive prompt. It displays the original Last.fm target alongside the Qobuz result, allowing you to manually approve or reject the track (`[y/n]`).

## 📦 Pre-built Binaries (Releases)

**For Windows x64 (10/11):**
👉 **[Download the latest ZIP here](https://github.com/Sei969/qobuz-dl/releases/latest)**
* **Portable:** No installation required.
* **Important:** Just extract the `.zip` and make sure `ffmpeg.exe` and `qobuz-dl-ultimate.exe` are in the same folder.

## 📥 Getting Started

> You'll need an **active subscription** to Qobuz.

#### Installation
Clone this repository and install the required dependencies:

```bash
git clone [https://github.com/Sei969/qobuz-dl.git](https://github.com/Sei969/qobuz-dl.git)
cd qobuz-dl
pip3 install -r requirements.txt
```

#### Run qobuz-dl
```bash
python -m qobuz_dl
```

## 💻 Download Usage

```text
usage: python -m qobuz_dl dl [-h] [-d PATH] [-q int] [--albums-only] [--no-m3u] [--no-fallback] [--no-db] 
                             [-ff PATTERN] [-tf PATTERN] [-s] [-e] [--no-cover]
                             [--embedded-art-size {50,100,150,300,600,max,org}] 
                             [--saved-art-size {50,100,150,300,600,max,org}] 
                             [--multiple-disc-prefix PREFIX] [--multiple-disc-one-dir] 
                             [--no-lyrics] [--native-lang] [--no-credits] [--delay SECONDS]
                             [--no-album-artist-tag] [--no-track-composer-tag] ... 
                             SOURCE [SOURCE ...]
```

### Key Arguments
* **Explicit Tag:** `{explicit}` or `{ExplicitFlag}`. Adds `[E]` if the content is explicit.
  * *Example:* `folder_format = {artist} - {album} {ExplicitFlag}`
* **Advanced Folder Formatting (`-ff`):** Support for `{album_artist}`, `{year}`, `{barcode}`, `{label}`, etc.
* **Advanced Track Formatting (`-tf`):** Support for `{track_number}`, `{track_title}`, `{isrc}`, etc.

## 🏆 Credits
* **[vitiko98](https://github.com/vitiko98/qobuz-dl)**: Creator of the original project.
* **[xwell](https://github.com/xwell/qobuz-dl)**: For the massive tag refactoring and "Goodies" integration.
* **[catap](https://github.com/catap)**: For the segmented download patch.

## ⚠️ Disclaimer
* This tool was written for educational purposes.
* `qobuz-dl` is not affiliated with Qobuz.