# qobuz-dl Ultimate Edition
[![PyPI version](https://img.shields.io/pypi/v/qobuz-dl-ultimate.svg)](https://pypi.org/project/qobuz-dl-ultimate/) [![PyPI Downloads](https://static.pepy.tech/personalized-badge/qobuz-dl-ultimate?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/qobuz-dl-ultimate) ![Docker Image CI](https://github.com/Sei969/qobuz-dl/actions/workflows/docker.yml/badge.svg) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Sei969/qobuz-dl/blob/master/Qobuz_Ultimate_Colab.ipynb)

Search, explore, and download Lossless and Hi-Res music from [Qobuz](https://www.qobuz.com/).

**This is an enhanced, feature-rich fork of the original qobuz-dl project, designed for the ultimate audiophile experience. It includes a resilient download engine with smart anti-spam filtering, deep customization for keeping your library perfectly organized, and extensive, native support for classical music metadata.**

## ✨ Features

### 🎧 Audiophile & Metadata Engine
* **Roon & DAP Optimized:** Metadata, cover art, and lyrics are meticulously formatted to ensure perfect out-of-the-box integration with Roon servers and Digital Audio Players.
* **Direct Album URL Tagging:** Automatically generates and embeds a direct, clickable `QOBUZ ALBUM URL` link directly into the track's metadata (Vorbis Comments for FLAC, `TXXX` frame for MP3). This allows one-click access to the original Qobuz album page directly from tag-editors like Mp3tag or compatible audiophile players. You can optionally disable this non-standard tag using the `--no-album-url-tag` flag (or `no_album_url_tag = true` in config).
* **Roon-Ready Synchronized Lyrics:** The engine intelligently formats and embeds timestamped `.lrc` data directly into the audio files (`[LYRICS]` Vorbis Comments), ensuring Roon natively displays scrolling, karaoke-style lyrics in its "Now Playing" view out-of-the-box. If you prefer a minimalist, clutter-free folder structure, you can disable the generation of external `.lrc` files entirely via CLI (`--no-lrc-files`). Conversely, if you prefer external files without bloating your audio metadata, use the new `--no-embed-lyrics` flag (or set `embed_lyrics = false` in your config).
* **Massive Tag Control:** Refactored tag engine supports highly detailed classical music metadata. Almost every single tag can be toggled on/off via CLI arguments.
* **Smart Genre Translation:** Automatically translates stubborn French genres (e.g., *Électronique*, *Bande Originale*) into standard English, ensuring your library remains consistent and searchable.
* **Native Multi-Artist & Multi-Value Tagging & Deep Performer Parsing:** Automatically detects and splits main artists, featured guests, and extracts *all* composers/lyricists from complex Qobuz metadata strings. With the new `--multi-tags` CLI flag, the engine intelligently splits comma-separated metadata into discrete multi-value tags for FLAC (Vorbis Comments) and MP3 (ID3v2.4), ensuring flawless library interpretation by high-end players like Roon, MusicBee, or Plexamp.
* **Native ReplayGain Support:** Automatically extracts and embeds `REPLAYGAIN_TRACK_GAIN` and `REPLAYGAIN_TRACK_PEAK` tags directly from Qobuz's hidden API data. This ensures perfect, non-destructive volume leveling out-of-the-box for high-end digital audio players (DAPs) and audiophile servers like Roon.
* **Automatic Lyrics Engine & Retroactive Tagger:** Fetches and injects synchronized (`.lrc`) and unsynchronized lyrics using LRCLIB (with a Genius fallback API). Includes a standalone `lyrics` command to retroactively scan and inject missing lyrics into your existing local library without re-downloading the audio.
* **Enhanced Digital Booklets:** Automatically compiles a beautifully formatted `.txt` file with a complete tracklist, runtime, full credits, metadata, and reviews. Upon completion, the engine intelligently sweeps the folder, strips timestamps from `.lrc` files, and appends the pure text lyrics of the entire album directly into the booklet. Official PDF "Goodies" are also downloaded alongside it. **You can now use the `--booklet-only` flag to exclusively download these metadata files, cover art, and PDFs while gracefully skipping all heavy audio tracks.**
* **Composer Field Fix:** Meticulously extracts every individual composer from the full performer string, ending the issue of truncated or "random" composer metadata.
* **Smart Date Formatting:** Standardizes release dates to single, clean entries, preventing duplicate year/date tag conflicts in playback software.
* **Bit-Perfect & Purist Mode:** Completely disable ReplayGain and Peak volume tags using the `--no-replaygain-tag` CLI flag (or `no_replaygain_tag = true` in config). This ensures your audio files remain strictly bit-perfect and untouched by any software volume-leveling instructions, ideal for high-end DACs and dedicated DAPs.

### 🚀 Resilient Download Engine
* **Bulletproof Queue:** Advanced track-level exception handling. If a single track is geo-blocked or missing from the servers (404 error), the engine gracefully skips it and seamlessly continues downloading the rest of your album or playlist without crashing.
* **Database Recovery & Sync:** Includes a specialized `--sync-db` engine to restore missing entries in your local database by scanning your existing music folders.
* **Bidirectional Playlist Sync (`sync-playlist`):** A powerful mirroring engine for dynamic playlists. Keep your local folders perfectly synced with online changes (downloading new tracks and cleanly deleting removed ones). **v2.0.1 introduces Smart Folder Logic:** when using `-d .` or generic paths, it automatically creates a subfolder named after the playlist, preventing accidental file deletions in your root directory.
* **Professional Missing Tracks Table:** If the sync engine detects tracks in your online playlist that are missing from your local drive, it now generates a clean, color-coded ASCII table with Title, Artist, and ID for easy tracking.
* **Smart Reverse Lookup:** Automatically identifies legacy files by reading their **ISRC** or **UPC** tags and querying the Qobuz API to restore the correct IDs into the database.
* **Smart Pre-Flight Config Validation:** Introduced in v2.0.3, an intelligent validation system scans your `config.ini` format strings before any downloads begin. If it detects an unrecognized variable, the engine gracefully aborts the process and uses `difflib` to smartly suggest the correct variable, preventing silent `KeyError` exceptions.
* **Segmented Download & Remuxing:** Bypasses Akamai CDN throttling with a high-speed segmented download engine and automatic FFmpeg remuxing.
* **Multithreaded Downloading:** Concurrent track downloads for blazing-fast album fetching.
* **Clean Multithreading UI:** Intelligently switches to a clutter-free, static logging system displaying precise file sizes (MB) during concurrent downloads. This prevents terminal visual glitches and "cursor wars" with the Lyrics Engine, while preserving the classic animated progress bars for sequential (`--delay`) downloads.
* **Terminal Recovery (Raw Mode Fix):** Resolved a critical UI bug where interrupting the interactive search prompt (`fun` mode) with `CTRL+C` would leave the OS terminal in a broken state. The engine now safely triggers a graceful system exit, restoring the terminal's default line discipline.
* **Smart Quality Fallback:** Automatically downgrades to the next best available quality if the requested tier is restricted by the server, ensuring your download queue never crashes.
* **Authentication Bypass:** Log in securely using your browser's **Auth Token** if standard password authentication is blocked. Graciously handles Free/Studio accounts.
* **Secure Credential Storage (OS Keyring):** Say goodbye to plaintext passwords. Authentication tokens (Qobuz and Genius) are securely encrypted and stored natively in your operating system's credential manager (Windows Credential Manager, macOS Keychain, or Linux Secret Service). **Ultimate Edition Feature:** Native support for headless environments (NAS/Docker/WSL). If the system lacks a secure keyring daemon, the engine provides a robust "Self-Healing" mechanism: it automatically detects the issue and offers a `disable_keyring` flag, allowing secure storage in `config.ini` and preventing persistent '401 Unauthorized' errors.
* **Anti-Ban Stealth Spoofing:** Modern WAF (Web Application Firewalls) block API requests originating from headless scripts. This engine features full cryptographic stealth spoofing, injecting exact Windows/Chrome Client Hints (`Sec-Ch-Ua`, `Sec-Fetch-Site`) to make your session completely indistinguishable from a legitimate user navigating the Qobuz Web Player, significantly reducing 403 errors and preventing account bans.
* **Limitless Playlists:** Overcomes Qobuz API restrictions by dynamically paginating chunk requests, allowing you to seamlessly queue and download massive playlists without the standard 50-track bottleneck.
* **Smart Resume (No Overwrites):** Intelligently detects existing files on your local drive and automatically skips them. If a massive discography download gets interrupted, it resumes instantly without wasting time or bandwidth re-downloading existing tracks.
* **Anti-Spam Blacklist Engine:** Automatically filter out unwanted "junk" releases (e.g., Karaoke versions, Instrumental Covers, Tribute albums) when downloading massive artist discographies or label catalogs. You can pass a `.txt` file containing your custom keywords (e.g., `Karaoke`, `(Live)`, `Original Soundtrack`) via the CLI flag `-b` or permanently set it in your `config.ini`. The engine dynamically joins the main title and version tags, ensuring flawless filtering before a single byte of audio is downloaded.
* **Stateful Batch Downloading (Text File Memory):** When downloading massive queues from a `.txt` file, the engine acts as a living database. It automatically validates URLs and appends a `[DONE]` tag next to completed links directly inside your text file. If your connection drops or you abort the process, simply re-run the command: the engine will instantly skip the completed links and seamlessly resume the queue exactly where it left off.
* **Flawless `.m3u` Generation:** Automatically generates playlist files with correct relative folder paths. **v2.0.1 features a robust 4-pass matching algorithm** (ID -> ISRC -> Title -> Filename) that guarantees the `.m3u` file perfectly mirrors the API order, even when tracks have no numerical prefixes in their filenames.
* **Ultra-Fast O(1) Matching Engine:** The playlist generator now uses high-performance dictionary indexing. It identifies local files instantly, reducing the processing time for massive playlists from seconds to milliseconds. (Thanks to marrobHD)
* **NAS & macOS Friendly Temporary Files:** Temporary download files now use a standard `~tmp_` prefix instead of a leading dot. This prevents Unix-based systems (macOS, Synology SMB/Samba) from permanently applying "Hidden" system attributes to your audio files, eliminating the need for terminal cleanup commands.

### 📁 Advanced Formatting & Storage

Qobuz-DL Ultimate allows deep customization of your library structure using variables.

* **True Playlist Support (Native):** Seamlessly handles Qobuz and Last.fm playlists with a specialized logic designed for library organization (Fixes #257).
  * **Flat Folder Structure:** Automatically downloads all tracks into a single directory named after the playlist, preventing the creation of dozens of scattered album sub-folders.
  * **Position-Independent Naming:** Audio files are saved cleanly (e.g., `Artist - Title.flac`) without hardcoded numerical prefixes. This industry-standard approach ensures that if a playlist changes order online, your local files are recognized instantly, preventing massive duplicate re-downloads.
  * **Smart API-Driven `.m3u`:** Playback order is guaranteed by a dynamically generated `.m3u` file that perfectly mirrors the exact sequence dictated by the Qobuz servers, regardless of the physical files' names.
  * **Smart Cover Management:** Eliminates the "Cover Conflict" bug. The engine dynamically manages embedded artwork, ensuring each track gets its correct unique cover without leaving duplicate `cover.jpg` files in the folder.
  * **Album Mode Override (`--playlist-as-albums`):** *New feature.* If you use playlists to hunt for specific songs, this flag completely bypasses the Flat Folder logic. The engine will "explode" the playlist, routing each track into its respective original album folder using your standard `folder_format`, keeping the original track numbers, and downloading the specific cover art for each album.
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
* **Legacy Character Replacement (`legacy_charmap`):** By default, the Ultimate Edition uses elegant fullwidth Unicode characters (e.g., `／`) to safely bypass OS filename restrictions without losing the original title's aesthetics. However, purists can activate the `legacy_charmap = true` option in their `config.ini` to enforce standard ASCII replacements (e.g., replacing `/` with `-` or stripping `?`), restoring the classic, old-school naming convention of the original qobuz-dl.

### ❤️ Native Favorites Sync & Interactive Menu
Seamlessly bridge your mobile listening habits with your local offline library. Instead of manually copying URLs, launch the Interactive Mode (`fun`) to securely access your personal Qobuz account and browse your **Favorite Albums, Tracks, Artists, and Playlists** directly from the terminal.
* **Zero-Typing Workflow:** Fetch your private library with a single click without ever leaving the terminal.
* **Massive Batch Downloading:** Use the `Spacebar` to multi-select dozens of your favorite releases from the clean, minimalist UI and queue them all up for download in seconds.
* **Smart Release Filter (Heuristic Engine):** When fetching an artist's discography, the engine runs a blazing-fast local heuristic algorithm to categorize releases (Albums, EPs, Singles, Live). It instantly presents a multi-select checkbox UI, allowing you to filter out unwanted singles or compilations before the download even begins, saving massive amounts of time and storage.

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

> **💡 Tip for Upgrading Users:** To access the latest configuration options (like `embed_lyrics` and `multi_value_tags`), simply run `qobuz-dl -r` to reset and regenerate a fresh `config.ini` file, or manually append them under the `[qobuz]` section.

```ini
[qobuz]
directory = ~/Music/Qobuz_Lossless

# Set to 'true' if running on a headless server (NAS/Docker/WSL) 
# to save tokens in config.ini instead of the OS Keyring.
disable_keyring = false

# Set to 'true' to restore classic ASCII character replacements
legacy_charmap = false

# Set to 'true' to disable external .lrc file generation
no_lrc_files = true

# Set to 'true' to restore classic ASCII character replacements (e.g. replacing '/' with '-')
legacy_charmap = false

# Set to 'true' to disable external .lrc file generation (lyrics will only be embedded in FLAC/MP3 tags)
no_lrc_files = true

# Set to 'true' to strictly disable ReplayGain volume tags for bit-perfect hardware playback
no_replaygain_tag = true

# Set to 'true' to disable writing the non-standard "QOBUZ ALBUM URL" tag into the files
no_album_url_tag = true

# Set to 'true' to disable classical music metadata extraction
no_conductor_tag = true
no_ensemble_tag = true
no_work_tag = true
```
*(Note: If you are upgrading from an older version, the legacy `default_folder` key is still fully supported for backward compatibility.)*

> **🔒 Security Note:** Your `auth_token` and `genius_token` will no longer be visible in your `config.ini`. The Ultimate Edition automatically migrates and encrypts them into your OS-level secure credential manager (Keyring) to protect your accounts.

### 🔑 How to get your Auth Token
Since Qobuz blocked direct password logins for third-party applications, you need to provide your browser's Auth Token during the initial configuration. Here is how to easily find it:
1. Open the [Qobuz Web Player](https://play.qobuz.com) in your browser and log in.
2. Press `F12` to open the Developer Tools.
3. Go to the **Application** tab (Chrome/Edge) or **Storage** tab (Firefox).
4. In the left sidebar, expand **Local Storage** and click on `https://play.qobuz.com`.
5. In the list of keys, find **`localuser`**.
6. At the bottom of the panel (or by expanding the JSON value), look for the **`token`** string.
7. Open your terminal and force the login wizard by running `qobuz-dl -r` (or `--reset`). When the prompt appears, select the Auth Token method and paste your alphanumeric string!

## 💻 Usage & Quick Examples

```text
[Global Commands & Database Management]
usage: python -m qobuz_dl [-h] [-r] [-p] [--sync-db [PATH]] [-sc] {interactive,i,fun,dl,lucky,lyrics,radar,sync-playlist,sp,stats} ...

[Download Usage]
usage: python -m qobuz_dl dl [-h] [-d PATH] [-q int] [--albums-only] [--no-m3u] [--no-fallback] [--no-db] 
                             [-ff PATTERN] [-tf PATTERN] [-s] [-e] [--no-cover]
                             [-b PATH]
                             [--embedded-art-size {50,100,150,300,600,max,org}] 
                             [--saved-art-size {50,100,150,300,600,max,org}] 
                             [--multiple-disc-prefix PREFIX] [--multiple-disc-one-dir] 
                             [--no-lyrics] [--no-lrc-files] [--native-lang] [--no-credits] [--with-credits] [--booklet-only] [--delay SECONDS] [--playlist-as-albums]
                             [--no-album-artist-tag] [--no-track-composer-tag] ... 
                             SOURCE [SOURCE ...]
```

**MusicButler Radar Mode:**
*(Tip: Run it once to save your RSS link, then run it daily to catch new releases and securely add them to your Qobuz favorites!)*
```bash
python -m qobuz_dl radar
```

**Bidirectional Playlist Sync:**
*(Tip: Add `-y` to bypass confirmation prompts. The `-d` flag acts securely, automatically creating a playlist subfolder).*
```bash
python -m qobuz_dl sp "URL" -d "C:\Path\To\Local\Playlist\Folder"
```
                            
**Basic Album/Playlist Download:**
```bash
python -m qobuz_dl dl [https://play.qobuz.com/album/qxjbxh1dc3xyb](https://play.qobuz.com/album/qxjbxh1dc3xyb)
```

**Explode Playlists into Albums:**
By default, playlists are downloaded into a single flat folder. Use this flag if you use playlists as a "discovery tool" and want the engine to dynamically route every single track into its respective original Album folder, complete with its specific cover art and original track metadata.
```bash
python -m qobuz_dl dl "PLAYLIST_URL" --playlist-as-albums
```

**Mass/Batch Downloading (Smart Resume):**
Do you have a massive list of releases to download? Create a standard text file (e.g., `list.txt`), paste your Qobuz **and Last.fm** URLs inside (one per line), and pass it to the engine. The smart parser will automatically download your Qobuz links and seamlessly route Last.fm playlists through the Fuzzy Matching engine to process your entire queue in one go!
*Ultimate Edition Feature:* The text file acts as a living database. As soon as a release or a full playlist is successfully downloaded, the engine appends a `[DONE]` tag next to its URL in the file. If your connection drops or you interrupt the process (`CTRL+C`), simply re-run the exact same command and the engine will instantly skip the completed links and seamlessly resume exactly where it left off.
```bash
python -m qobuz_dl dl list.txt
```

**Discography Blacklist & Anti-Spam Mode:**
Downloading a massive artist discography but want to avoid wasting space on Karaoke, Tribute, or Instrumental versions? Create a text file (e.g., `blacklist.txt`) containing your unwanted keywords (one per line) and pass it to the engine. It will automatically inspect every release and seamlessly skip the junk!
*(Tip: You can set `blacklist = blacklist.txt` in your `config.ini` to make this automatic for every download).*
```bash
python -m qobuz_dl dl [https://play.qobuz.com/artist/123456](https://play.qobuz.com/artist/123456) -b blacklist.txt
```

**Ultimate Anti-Ban Mode (Stealth + Delay):**
While the engine natively masks your digital footprint (Stealth Spoofing) to simulate a real Chrome browser, downloading 100 tracks in 10 seconds is still physically impossible for a human and can trigger volume-based bans. Use this command for massive discographies to disable multithreading and add a forced cooldown between tracks, ensuring maximum account safety.
```bash
python -m qobuz_dl dl <URL> --delay 1
```

**Force Booklets & Credits (Config Override):**
If you have set `no_credits = true` in your `config.ini` to keep your folders clean, you can temporarily override this behavior to force the generation of the Digital Booklet and Tracklist.txt for a specific masterpiece.
```bash
python -m qobuz_dl dl <URL> --with-credits
```

**Multi-Tag & Performer Parsing:**
Use the `--multi-tags` flag to ensure that complex tracks with multiple artists and composers are split into clean, individual fields in your audio tags.
```bash
python -m qobuz_dl dl "URL" --multi-tags
```

**Metadata & Booklet Only Mode:**
Want to complete your library's metadata without downloading gigabytes of audio? This command fetches only the cover art, generates the Tracklist/Credits booklet, downloads official PDF Goodies, and gracefully skips all audio tracks.
```bash
python -m qobuz_dl dl [https://play.qobuz.com/album/qxjbxh1dc3xyb](https://play.qobuz.com/album/qxjbxh1dc3xyb) --booklet-only
```

**Minimalist Folder Mode (No external .lrc files):**
Downloads the album and injects synchronized lyrics purely into the FLAC/MP3 metadata, keeping your folders completely clean from external text files.
```bash
python -m qobuz_dl dl [https://play.qobuz.com/album/qxjbxh1dc3xyb](https://play.qobuz.com/album/qxjbxh1dc3xyb) --no-lrc-files
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
**Audiophile Purist Mode (No ReplayGain):**
Download a track keeping the file strictly bit-perfect without writing any volume-leveling tags (useful for hardware DSPs and DAPs).
```bash
python -m qobuz_dl dl "URL" --no-replaygain-tag
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
  python -m qobuz_dl sp "PLAYLIST_URL" -d "/path/to/your/local/folder"
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

* **User Statistics (`stats`):**
  Curious about your downloading habits? This command instantly queries your local SQLite database to display your download statistics, including the total number of unique artists fetched and a complete alphabetical list of your library.
  ```bash
  python -m qobuz_dl stats
  ```

### 🛠️ Key Formatting Variables

You can deeply customize your `config.ini` or use the CLI flags `-ff` (Folder Format) and `-tf` (Track Format) using the variables below. You can also use the `/` character to automatically create nested subdirectories!

#### 📝 Complete Variables Reference Table

| Variable | Description | Example Output |
| :--- | :--- | :--- |
| **Artists & Composers** | | |
| `{album_artist}` | The main artist of the album (handles compilations gracefully). | `Daft Punk` |
| `{artist}` / `{track_artist}` | The performing artist of the specific track. | `Pharrell Williams` |
| `{album_composer}` | The composer of the entire album/work. | `Thomas Bangalter` |
| `{track_composer}` | The composer of the specific track. | `Guy-Manuel de Homem-Christo` |
| **Titles & Versions** | | |
| `{album}` / `{album_title}` | Album title (includes version like "Remastered" if present). | `Random Access Memories (Deluxe)` |
| `{album_title_base}` | Base album title strictly *without* the version details. | `Random Access Memories` |
| `{track_title}` / `{tracktitle}`| Track title (includes version if present). | `Get Lucky (Radio Edit)` |
| `{track_title_base}` | Base track title strictly *without* the version details. | `Get Lucky` |
| `{version}` / `{album_version}` | Just the version string. | `Deluxe` |
| `{version_tag}` | Smart version tag (prepends a dash: ` - Deluxe`). Leaves no trailing spaces if empty! | ` - Deluxe` |
| **Numbers & Dates** | | |
| `{track_number}` | The track number (always padded with leading zero). | `08` |
| `{disc_number}` | The disc media number (padded with leading zero). | `01` |
| `{track_count}` | Total number of tracks in the album. | `13` |
| `{disc_count}` | Total number of discs in the album. | `1` |
| `{year}` | The release year. | `2013` |
| `{release_date}` | The full original release date. | `2013-05-17` |
| **Technical Specs** | | |
| `{media_type}` | Raw product type extracted from the API (capitalized). | `Album` |
| `{quality_tag}` | Smart tag combining format and bit depth (clean MP3 fallback). | `FLAC 24` |
| `{album_url}` | The official Qobuz URL of the release. | `https://play.qobuz.com/...` |
| `{bit_depth}` | The audio bit depth. | `24` |
| `{sampling_rate}` | The audio sampling rate in kHz. | `88.2` |
| `{format}` | The downloaded file format. | `FLAC` |
| **Metadata & IDs** | | |
| `{release_type}` | Smart release type classification (`Album`, `EP`, `Single`). | `Album` |
| `{explicit}` / `{ExplicitFlag}`| Adds an `[E]` tag if parental advisory is active (empty if clean). | `[E]` |
| `{album_genre}` | Primary genre of the release. | `Electronic` |
| `{label}` | The record label name. | `Columbia` |
| `{copyright}` | Copyright string. | `℗ 2013 Daft Life` |
| `{barcode}` / `{upc}` | The global UPC/Barcode of the release. | `888837168618` |
| `{isrc}` | The unique ISRC identifier of the track. | `USSM11302305` |
| `{album_id}` / `{track_id}` | Qobuz internal database IDs. | `123456789` |

#### 💡 Real-World Examples

**1. The "Audiophile Archive" Strategy (Nested Folders)**
Sorts by Genre, then Artist, then Album with full technical specs:
* `folder_format = {album_genre}/{album_artist}/{album_artist} - {album_title}{version_tag} ({year}) [{bit_depth}B-{sampling_rate}kHz]`
* Output: `Electronic/Daft Punk/Daft Punk - Random Access Memories - Deluxe (2013) [24B-88.2kHz]`

**2. The "Clean Library" Strategy (Smart Explicit/Version Tags)**
Keeps it simple but adds `[E]` only if explicit, and versions without leaving empty dashes:
* `folder_format = {album_artist} - {album_title_base}{version_tag} {ExplicitFlag}`
* Output: `Eminem - The Eminem Show [E]`

**3. The "Archivist" Track Strategy**
* `track_format = {track_number} - {track_title} [{isrc}]`
* Output: `08 - Get Lucky [USSM11302305].flac`

## 🔧 Troubleshooting: Headless & Server Environments
If you are running `qobuz-dl` on a NAS, Docker, or a headless Linux system (like WSL without a GUI keyring daemon), you might encounter `401 Unauthorized` errors after a configuration reset.

**The Fix:**
When running `python -m qobuz_dl -r`, the configuration wizard will now ask: 
`"Disable OS Keyring and save tokens in config.ini?"` 
Select **`yes`** if you are on a server or NAS environment. This will bypass the system keyring and ensure your tokens are persisted in the `config.ini` file, guaranteeing 100% stable authentication

## 👨‍💻 For Developers: Using Qobuz-DL as a Python Library

Are you building your own music automation scripts, Telegram bots, or Discord integrations? 
You can import our core engines (AES-Segmented Downloader, Audiophile Tagger, and WAF-Bypass Client) directly into your own Python projects!

📚 **[Read the Official Developer API Guide in our Wiki](https://github.com/Sei969/qobuz-dl/wiki/Developer-Guide-(Python-API))**

## 🏆 Credits
* **[vitiko98](https://github.com/vitiko98/qobuz-dl)**: Creator of the original project.
* **[xwell](https://github.com/xwell/qobuz-dl)**: For the massive tag refactoring and "Goodies" integration.
* **[catap](https://github.com/catap)**: For the segmented download patch.
* **JosiahDanger**: Bug reports and feature suggestions.
* **Sorrow446 & DashLt**: `qobuz-dl` is inspired by the discontinued Qo-DL-Reborn. This tool uses the core API module `qopy`, originally written by them.

## ⚠️ Disclaimer
* This tool was written for educational purposes.
* `qobuz-dl` is not affiliated with Qobuz.