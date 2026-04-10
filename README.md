# qobuz-dl Ultimate
Search, explore, and download Lossless and Hi-Res music from [Qobuz](https://www.qobuz.com/).
This is an enhanced, feature-rich fork of the original qobuz-dl project, designed for the ultimate audiophile experience.

## Features & Ultimate Additions

* **[NEW] Automatic Lyrics Engine:** Fetches and injects synchronized (`.lrc`) and unsynchronized lyrics using LRCLIB (with a Genius fallback API).
* **[NEW] Digital Booklet Generation:** Automatically compiles a `.txt` file with a complete tracklist (including track durations), full credits, metadata, and album reviews for every download.
* **[NEW] Segmented Download & Remuxing:** Bypasses Akamai CDN throttling with a high-speed, multithreaded segmented download engine and automatic FFmpeg remuxing.
* **[NEW] Smart Quality Fallback:** Automatically downgrades to the next best available quality if the requested tier is restricted by the server, ensuring your download queue never crashes.
* **[NEW] Token Authentication:** Log in securely using your browser's `user_auth_token` if standard password authentication is blocked by Qobuz.
* **[NEW] Regional Bypass:** Forces English language for metadata, reviews, and digital booklets regardless of your account's native region.
* Download FLAC and MP3 files from Qobuz
* Explore and download music directly from your terminal with **interactive** or **lucky** mode
* Download albums, tracks, artists, playlists, and labels with **download** mode
* Download music from last.fm playlists
* Queue support on **interactive** mode
* Effective duplicate handling with own portable database
* Support for albums with multiple discs and M3U playlists
* Downloads URLs from text files
* Extended tags and more...

## Getting started

> You'll need an **active subscription** to Qobuz.

#### Installation
Clone this repository and install the required dependencies:
```bash
git clone [https://github.com/Sei969/qobuz-dl.git](https://github.com/Sei969/qobuz-dl.git)
cd qobuz-dl
pip3 install -r requirements.txt