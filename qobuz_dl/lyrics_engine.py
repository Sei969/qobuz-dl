import os
import requests
import mutagen
from mutagen.id3 import ID3, USLT, ID3NoHeaderError
from mutagen.flac import FLAC

# Import lyricsgenius only if the user has configured the token
try:
    import lyricsgenius
except ImportError:
    lyricsgenius = None


class LyricsEngine:
    """
    Roon-Ready Synchronized Lyrics Engine.
    
    Responsible for fetching synchronized (LRC) or plain text lyrics from LRCLIB 
    and falling back to Genius API if configured. It handles both saving external 
    .lrc/.txt files and natively embedding the lyrics into audio metadata.
    """

    def __init__(self, genius_token=None):
        """
        Initializes the Lyrics Engine and conditionally loads the Genius API client.

        Args:
            genius_token (str, optional): The user's Genius API token. Defaults to None.
        """
        self.genius_token = genius_token
        self.genius = None
        if self.genius_token and lyricsgenius:
            self.genius = lyricsgenius.Genius(self.genius_token, remove_section_headers=True)
            self.genius.verbose = False

    def fetch_and_inject(self, file_path, artist, track, album, save_lrc=True, embed_lyrics=True):
        """
        Waterfall engine: first try LRCLIB (for LRC format), then Genius.
        
        Attempts to fetch lyrics for the given track. If synchronized lyrics are found, 
        they can be saved as a separate .lrc file and/or embedded into the audio file's tags 
        for native Karaoke support in Roon and advanced DAPs.

        Args:
            file_path (str): The absolute path to the audio file.
            artist (str): The name of the main artist.
            track (str): The track title.
            album (str): The album title.
            save_lrc (bool, optional): If True, saves an external .lrc or .txt file next to the audio. Defaults to True.
            embed_lyrics (bool, optional): If True, injects the lyrics into the audio file's metadata. Defaults to True.
        """
        
        if not save_lrc and not embed_lyrics:
            return
            
        try:
            print(f"    🔍 Searching lyrics for: {track}...")
            
            lrclib_url = "https://lrclib.net/api/get"
            headers = {"User-Agent": "qobuz-dl-ultimate/1.0 (https://github.com/Sei969/qobuz-dl)"}
            
            params = {"artist_name": artist, "track_name": track, "album_name": album}
            response = requests.get(lrclib_url, params=params, headers=headers, timeout=12) 
            
            if response.status_code != 200:
                params = {"artist_name": artist, "track_name": track}
                response = requests.get(lrclib_url, params=params, headers=headers, timeout=12)

            if response.status_code == 200:
                data = response.json()
                synced_lyrics = data.get("syncedLyrics")
                plain_lyrics = data.get("plainLyrics")
                
                if synced_lyrics:
                    if embed_lyrics:
                        self._inject_metadata(file_path, synced_lyrics)
                    if save_lrc:
                        self._save_lrc_file(file_path, synced_lyrics)
                        
                    if embed_lyrics and save_lrc:
                        print(f"    ✅ Synchronized lyrics injected and saved as .lrc!")
                    elif save_lrc:
                        print(f"    ✅ Synchronized lyrics saved as .lrc (Embedding disabled)!")
                    elif embed_lyrics:
                        print(f"    ✅ Synchronized lyrics injected into metadata!")
                    return
                    
                elif plain_lyrics:
                    if embed_lyrics:
                        self._inject_metadata(file_path, plain_lyrics)
                    if save_lrc:
                        self._save_lrc_file(file_path, plain_lyrics)

                    if embed_lyrics and save_lrc:
                        print(f"    ✅ Standard lyrics injected and saved as .txt!")
                    elif save_lrc:
                        print(f"    ✅ Standard lyrics saved as .txt (Embedding disabled)!")
                    elif embed_lyrics:
                        print(f"    ✅ Standard lyrics injected into metadata!")
                    return

            if self.genius:
                song = self.genius.search_song(track, artist)
                if song and song.lyrics:
                    if embed_lyrics:
                        self._inject_metadata(file_path, song.lyrics)
                    if save_lrc:
                        self._save_lrc_file(file_path, song.lyrics)
                        
                    if embed_lyrics and save_lrc:
                        print(f"    ✅ Lyrics injected via Genius and saved!")
                    elif save_lrc:
                        print(f"    ✅ Lyrics saved via Genius (Embedding disabled)!")
                    elif embed_lyrics:
                        print(f"    ✅ Lyrics injected via Genius (Fallback)!")
                    return

            print(f"    ❌ No lyrics found for this track.")

        except Exception as e:
            print(f"    ⚠️ Error during lyrics search: {e}")

    def _save_lrc_file(self, audio_file_path, synced_lyrics):
        """
        Creates the .lrc or .txt file next to the audio file.

        Args:
            audio_file_path (str): The absolute path to the downloaded audio file.
            synced_lyrics (str): The lyrics string to be saved.
        """
        base_name = os.path.splitext(audio_file_path)[0]
        lrc_path = f"{base_name}.lrc"
        with open(lrc_path, 'w', encoding='utf-8') as f:
            f.write(synced_lyrics)

    def _inject_metadata(self, file_path, lyrics):
        """
        Injects lyrics directly into FLAC (LYRICS block) or MP3 (USLT frame) tags.

        Args:
            file_path (str): The absolute path to the downloaded audio file.
            lyrics (str): The fetched lyrics string.
        """
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
            pass # Ignore writing errors to avoid crashing the program