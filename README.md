# qobuz-dl Ultimate Edition
Search, explore, and download Lossless and Hi-Res music from [Qobuz](https://www.qobuz.com/).

**This is an enhanced, feature-rich fork of the original qobuz-dl project, designed for the ultimate audiophile experience. It includes a resilient download engine, deep customization for keeping your library perfectly organized, and extensive, native support for classical music metadata.**

## ✨ Features

### 🎧 Audiophile & Metadata Engine
* **Roon & DAP Optimized:** Metadata, cover art, and lyrics are meticulously formatted to ensure perfect out-of-the-box integration with Roon servers and Digital Audio Players.
* **Massive Tag Control:** Refactored tag engine supports highly detailed classical music metadata. Almost every single tag can be toggled on/off via CLI arguments.
* **Automatic Lyrics Engine:** Fetches and injects synchronized (`.lrc`) and unsynchronized lyrics using LRCLIB (with a Genius fallback API).
* **Digital Booklets & Goodies:** Automatically compiles a `.txt` file with a complete tracklist, full credits, metadata, and reviews, while simultaneously downloading official PDF "Goodies" (Booklets).
* **FLAC Integrity:** Added option to fix MD5 checksums for FLAC files.

### 🚀 Resilient Download Engine
* **Segmented Download & Remuxing:** Bypasses Akamai CDN throttling with a high-speed segmented download engine and automatic FFmpeg remuxing.
* **Multithreaded Downloading:** Concurrent track downloads for blazing-fast album fetching.
* **Smart Quality Fallback:** Automatically downgrades to the next best available quality if the requested tier is restricted by the server, ensuring your download queue never crashes.
* **Authentication Bypass:** Log in securely using your browser's `user_auth_token` if standard password authentication is blocked. Graciously handles Free/Studio accounts.

### 📁 Advanced Formatting & Storage
* **Powerful Variables:** `folder_format` and `track_format` now support dozens of new variables (e.g., `{isrc}`, `{barcode}`, `{label}`, `{track_composer}`).
* **Multi-Disc Routing:** Store multiple disc releases in one single directory or split them using customizable prefixes (e.g., `CD 01`). By default, multi-disc releases are neatly split into separate sub-directories (e.g., `Disc 01`, `Disc 02`). You can control this behavior via your configuration file (`config.ini` or `qobuz_dl/settings.py`):
  * **Merge into a single folder:** Change `multiple_disc_one_dir = False` ➡️ `True`.
  * **Change the sub-folder name:** Change `multiple_disc_prefix = Disc` ➡️ `CD` (or your preferred naming convention).
* **Cover Art Sizing:** Granular control over the resolution of embedded artwork vs. locally saved artwork (e.g., `600`, `max`, `org`).
* **Regional Bypass:** Forces English language for metadata, reviews, and digital booklets regardless of your account's native region (can be toggled off).

## 🌉 Last.fm Smart Integration
Import your personalized Last.fm playlists directly into Qobuz! **The original legacy implementation has been entirely removed and replaced by a modern, ground-up refactor to ensure superior stability and performance.** Simply paste a Last.fm playlist URL, and the engine will intelligently bridge the two platforms, finding and downloading the highest quality equivalents.

### Smart Track Matching & Interactive Mode
Track names often differ slightly between platforms (e.g., missing "Remastered" tags, differently formatted featured artists). To prevent downloading incorrect songs (like live covers or techno remixes), this fork utilizes a mathematical **Fuzzy Matching Algorithm**:

* **Auto-Accept (> 75% similarity):** Perfect or near-perfect matches are automatically queued and downloaded.
* **Auto-Skip (< 60% similarity):** Completely wrong tracks are automatically skipped, keeping your hard drive clean.
* **Interactive Selection (60% - 74% similarity):** For borderline matches, the engine pauses and activates an interactive prompt. It displays the original Last.fm target alongside the Qobuz result, allowing you to manually approve or reject the track (`[y/n]`).

**Usage:**
    python -m qobuz_dl dl https://www.last.fm/user/<your profile>/playlists/<playlist_id>

## 📥 Getting Started

> You'll need an **active subscription** to Qobuz.

#### Installation
Clone this repository and install the required dependencies:

    git clone https://github.com/Sei969/qobuz-dl.git
    cd qobuz-dl
    pip3 install -r requirements.txt

*(Windows users may also need to run `pip3 install windows-curses` for interactive mode).*

#### Run qobuz-dl
To ensure maximum compatibility and avoid namespace conflicts, it is recommended to run the script as a Python module from the root folder:

    python -m qobuz_dl

> If something fails, run `python -m qobuz_dl -r` to reset your config file and launch the interactive setup wizard.

## 💻 Usage & CLI Arguments

    usage: python -m qobuz_dl dl [-h] [-d PATH] [-q int] [--albums-only] [--no-m3u] [--no-fallback] [--no-db] 
                                 [-ff PATTERN] [-tf PATTERN] [-s] [--fix-md5s] [-e] [--no-cover]
                                 [--embedded-art-size {50,100,150,300,600,max,org}] 
                                 [--saved-art-size {50,100,150,300,600,max,org}] 
                                 [--multiple-disc-prefix PREFIX] [--multiple-disc-one-dir] 
                                 [--no-lyrics] [--native-lang] [--no-credits]
                                 [--no-album-artist-tag] [--no-track-composer-tag] ... 
                                 SOURCE [SOURCE ...]

### Advanced Formatting Keys
* **Folder Formatting (`-ff`):** `{album_artist}`, `{album_title}`, `{year}`, `{barcode}`, `{album_genre}`, `{label}`, `{upc}`, `{release_date}`, `{media_type}`, `{format}`, `{bit_depth}`, `{sampling_rate}`, `{disc_count}`, `{track_count}`.
* **Track Formatting (`-tf`):** `{track_number}`, `{track_title}`, `{track_artist}`, `{track_composer}`, `{isrc}`, `{disc_number}`.
*(Note: System-reserved characters like `/:<>` are automatically sanitized).*

## 💡 Examples

**Standard Hi-Res Download:**

    python -m qobuz_dl dl https://play.qobuz.com/album/qxjbxh1dc3xyb -q 27

**Last.fm Playlist Import:**

    python -m qobuz_dl dl https://www.last.fm/user/vitiko98/playlists/11887574

**Ultimate Customization (No lyrics, no booklets, native language metadata):**

    python -m qobuz_dl dl https://play.qobuz.com/album/qxjbxh1dc3xyb --no-lyrics --no-credits --native-lang

**Advanced Discography Routing (Save multiple discs in one folder, fix FLAC MD5):**

    python -m qobuz_dl dl https://play.qobuz.com/artist/2038380 --multiple-disc-one-dir --fix-md5s

**Interactive Mode:**

    python -m qobuz_dl fun -l 10

*(Tip: In interactive mode, use `Space` to multi-select several albums to download at once!)*

## 🏆 Credits
* **[vitiko98](https://github.com/vitiko98/qobuz-dl)**: The creator of the original `qobuz-dl` project. A huge thanks for laying the foundation of this amazing tool.
* **[xwell](https://github.com/xwell/qobuz-dl)**: For of the massive tag refactoring, customizable metadata engine, dynamic formatting variables, and "Goodies" integration.
* **[catap](https://github.com/catap)**: For the segmented download patch, which bypasses the Akamai CDN throttling.

*`qobuz-dl` is also inspired by the discontinued Qo-DL-Reborn (using modules `qopy` and `spoofer` by Sorrow446 and DashLt).*

## ⚠️ Disclaimer
* This tool was written for educational purposes. I will not be responsible if you use this program in bad faith. By using it, you are accepting the [Qobuz API Terms of Use](https://static.qobuz.com/apps/api/QobuzAPI-TermsofUse.pdf).
* `qobuz-dl` is not affiliated with Qobuz.