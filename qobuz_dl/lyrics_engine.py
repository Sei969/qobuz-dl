import os
import requests
import difflib
import mutagen
from mutagen.id3 import ID3, USLT, ID3NoHeaderError
from mutagen.flac import FLAC
from qobuz_dl.color import OFF, GREEN, RED, YELLOW, CYAN

# Import lyricsgenius only if the user has configured the token
try:
    import lyricsgenius
except ImportError:
    lyricsgenius = None


class LyricsEngine:
    """
    Roon-Ready Synchronized Lyrics Engine with Fuzzy Matching Security.
    Now prioritizing Official Qobuz Native Lyrics as the primary source.
    """

    def __init__(self, genius_token=None):
        self.genius_token = genius_token
        self.genius = None
        if self.genius_token and lyricsgenius:
            self.genius = lyricsgenius.Genius(self.genius_token, remove_section_headers=True)
            self.genius.verbose = False

    def _verify_match(self, req_artist, req_track, res_artist, res_track, is_parallel=False):
        """
        Fuzzy Matching Algorithm to prevent injecting wrong lyrics.
        Context-Aware: auto-skips borderline matches during parallel execution to prevent deadlocks.
        """
        if not res_artist or not res_track:
            return False

        req_a_clean, req_t_clean = req_artist.lower().strip(), req_track.lower().strip()
        res_a_clean, res_t_clean = res_artist.lower().strip(), res_track.lower().strip()

        # Calculate similarity ratios
        artist_ratio = difflib.SequenceMatcher(None, req_a_clean, res_a_clean).ratio()
        track_ratio = difflib.SequenceMatcher(None, req_t_clean, res_t_clean).ratio()
        
        # Weighted average (track name is slightly more important for lyrics)
        match_percentage = ((artist_ratio * 0.4) + (track_ratio * 0.6)) * 100

        if match_percentage >= 75.0:
            return True
        elif 60.0 <= match_percentage < 75.0:
            if is_parallel:
                # BATCH UNATTENDED MODE: Skip without prompting to prevent thread stalling
                print(f"    ⚠️ [LYRICS RADAR] Borderline match ({match_percentage:.1f}%). Auto-skipping in parallel mode.")
                return False
            else:
                # SEQUENTIAL MODE: Interactive confirmation
                print(f"\n{YELLOW}    ⚠️ [LYRICS RADAR] Borderline match detected ({match_percentage:.1f}%){OFF}")
                print(f"       Requested : {req_artist} - {req_track}")
                print(f"       Found     : {res_artist} - {res_track}")
                
                while True:
                    choice = input(f"       {CYAN}Accept these lyrics? [y/N]: {OFF}").lower().strip()
                    if choice in ['y', 'yes']:
                        return True
                    elif choice in ['n', 'no', '']:
                        return False
        else:
            print(f"    ❌ Lyrics skipped: Too different ({res_artist} - {res_track} | {match_percentage:.1f}%)")
            return False

    def fetch_and_inject(self, file_path, artist, track, album, save_lrc=True, embed_lyrics=True, is_parallel=False, track_id=None, qobuz_client=None):
        """
        Orchestrates the retrieval and injection of synchronized lyrics.
        Prioritizes Native Qobuz Lyrics -> LRCLIB Fallback -> Genius API.
        """
        if not save_lrc and not embed_lyrics:
            return
            
        try:
            print(f"    🔍 Searching lyrics for: {track}...")
            
            # --- 1. QOBUZ NATIVE LYRICS (PRIMARY SOURCE) ---
            if qobuz_client and track_id:
                qobuz_lyrics = self._fetch_qobuz_native(qobuz_client, track_id)
                if qobuz_lyrics:
                    if embed_lyrics: self._inject_metadata(file_path, qobuz_lyrics)
                    if save_lrc: self._save_lrc_file(file_path, qobuz_lyrics)
                    print(f"    ✅ Official Qobuz lyrics injected (Native 1:1 sync)!")
                    return

            # --- 2. FALLBACK TO LRCLIB ---
            lrclib_url = "https://lrclib.net/api/get"
            headers = {"User-Agent": "qobuz-dl-ultimate/2.0 (https://github.com/Sei969/qobuz-dl)"}
            
            params = {"artist_name": artist, "track_name": track, "album_name": album}
            response = requests.get(lrclib_url, params=params, headers=headers, timeout=12) 
            
            if response.status_code != 200:
                params = {"artist_name": artist, "track_name": track}
                response = requests.get(lrclib_url, params=params, headers=headers, timeout=12)

            if response.status_code == 200:
                data = response.json()
                
                # --- FUZZY MATCHING SECURITY CHECK (LRCLIB) ---
                api_artist = data.get("artistName", "")
                api_track = data.get("trackName", "")
                
                if self._verify_match(artist, track, api_artist, api_track, is_parallel):
                    synced_lyrics = data.get("syncedLyrics")
                    plain_lyrics = data.get("plainLyrics")
                    
                    if synced_lyrics:
                        if embed_lyrics: self._inject_metadata(file_path, synced_lyrics)
                        if save_lrc: self._save_lrc_file(file_path, synced_lyrics)
                        print(f"    ✅ Synchronized lyrics injected (LRCLIB fallback)!")
                        return
                        
                    elif plain_lyrics:
                        if embed_lyrics: self._inject_metadata(file_path, plain_lyrics)
                        if save_lrc: self._save_lrc_file(file_path, plain_lyrics)
                        print(f"    ✅ Standard lyrics injected (LRCLIB fallback)!")
                        return

            # --- 3. FALLBACK TO GENIUS ---
            if self.genius:
                song = self.genius.search_song(track, artist)
                if song and song.lyrics:
                    # --- FUZZY MATCHING SECURITY CHECK (GENIUS) ---
                    if self._verify_match(artist, track, song.artist, song.title, is_parallel):
                        if embed_lyrics: self._inject_metadata(file_path, song.lyrics)
                        if save_lrc: self._save_lrc_file(file_path, song.lyrics)
                        print(f"    ✅ Lyrics injected via Genius and saved!")
                        return

            print(f"    ❌ No valid lyrics found for this track.")

        except Exception as e:
            print(f"    ⚠️ Error during lyrics search: {e}")

    def _save_lrc_file(self, audio_file_path, lyrics):
        """Saves a standalone .lrc text file alongside the audio."""
        base_name = os.path.splitext(audio_file_path)[0]
        lrc_path = f"{base_name}.lrc"
        with open(lrc_path, 'w', encoding='utf-8') as f:
            f.write(lyrics)

    def _inject_metadata(self, file_path, lyrics):
        """Injects lyrics into the Vorbis or ID3v2 container."""
        if not lyrics: return
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == '.flac':
                audio = FLAC(file_path)
                audio['LYRICS'] = lyrics
                audio.save()
            elif ext == '.mp3':
                try:
                    audio = ID3(file_path)
                except ID3NoHeaderError:
                    audio = ID3()
                audio.add(USLT(encoding=3, lang='eng', desc='', text=lyrics))
                audio.save(file_path)
        except Exception:
            pass

    def _fetch_qobuz_native(self, qobuz_client, track_id):
        """
        Fetches official synchronized lyrics directly from Qobuz CDN.
        Uses the authenticated client to request the presigned CloudFront URL.
        """
        try:
            # Assuming 'qobuz_client' exposes a generic '.request()' method 
            # to handle MD5 signature and timestamp injection for custom endpoints.
            # (Note: If 'qopy' requires a specific method for this, we will implement it in the client)
            resp = qobuz_client.api_call("track/lyricsUrl", track_id=track_id)
            
            if not resp or "lyrics_url" not in resp:
                return None
                
            lyrics_url = resp.get("lyrics_url")
            if not lyrics_url:
                return None
                
            # Bare GET request to CloudFront CDN (No Qobuz Auth Headers required here)
            cdn_resp = requests.get(lyrics_url, timeout=10)
            if cdn_resp.status_code != 200:
                return None
                
            doc = cdn_resp.json()
            return self._parse_qobuz_to_lrc(doc)
            
        except Exception:
            # Silent fallback if Qobuz API fails or track has no native lyrics
            return None

    def _parse_qobuz_to_lrc(self, doc):
        """
        Converts Qobuz millisecond timestamp format into standard LRC format [mm:ss.xx].
        Supports plain text payload (non-synchronized) as a fallback.
        """
        original = doc.get("original", {})
        lines = original.get("lines", [])
        
        if not lines:
            return None
            
        lrc_lines = []
        for entry in lines:
            text = entry.get("line", "").strip()
            start_ms = entry.get("start")
            
            if start_ms is not None:
                total_seconds = start_ms / 1000.0
                minutes = int(total_seconds // 60)
                seconds = total_seconds % 60
                # Format to standard LRC timestamp: [mm:ss.xx]
                timestamp = f"[{minutes:02d}:{seconds:05.2f}]"
                lrc_lines.append(f"{timestamp} {text}")
            else:
                # Unsynchronized text fallback
                lrc_lines.append(text)
                
        return "\n".join(lrc_lines).strip()