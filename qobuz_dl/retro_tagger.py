import os
import logging
from mutagen.flac import FLAC
import mutagen.id3 as id3
from mutagen.id3 import ID3NoHeaderError

from qobuz_dl.lyrics_engine import LyricsEngine
from qobuz_dl.color import CYAN, GREEN, YELLOW, RED, OFF

logger = logging.getLogger(__name__)

def inject_lyrics_retroactively(directory_path, genius_token=None):
    print(f"\n{CYAN}[*] Starting retroactive lyrics scan in: {directory_path}{OFF}")
    
    if not os.path.isdir(directory_path):
        print(f"{RED}[!] Error: The directory '{directory_path}' does not exist.{OFF}")
        return

    engine = LyricsEngine(genius_token)
    processed = 0
    injected = 0
    skipped = 0
    
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith((".flac", ".mp3")):
                file_path = os.path.join(root, file)
                processed += 1
                
                try:
                    title, artist, album = "", "", ""
                    needs_lyrics = False

                    # --- FLAC HANDLING ---
                    if file.lower().endswith(".flac"):
                        audio = FLAC(file_path)
                        # Check if lyrics are already present
                        if audio.get("LYRICS") or audio.get("UNSYNCEDLYRICS"):
                            skipped += 1
                            continue
                            
                        title = audio.get("TITLE", [""])[0]
                        artist = audio.get("ARTIST", [""])[0]
                        album = audio.get("ALBUM", [""])[0]
                        needs_lyrics = True
                        
                    # --- MP3 HANDLING ---
                    elif file.lower().endswith(".mp3"):
                        try:
                            audio = id3.ID3(file_path)
                        except ID3NoHeaderError:
                            skipped += 1
                            continue
                            
                        # Check if lyrics are already present (USLT = unsynced, SYLT = synced)
                        if audio.getall("USLT") or audio.getall("SYLT"):
                            skipped += 1
                            continue
                            
                        title = audio.get("TIT2").text[0] if audio.get("TIT2") else ""
                        artist = audio.get("TPE1").text[0] if audio.get("TPE1") else ""
                        album = audio.get("TALB").text[0] if audio.get("TALB") else ""
                        needs_lyrics = True

                    # Skip if file is corrupted or lacks basic tags
                    if not title or not artist:
                        skipped += 1
                        continue
                        
                    # --- LYRICS INJECTION ---
                    if needs_lyrics:
                        print(f"{YELLOW}  > Missing lyrics: {artist} - {title}. Searching...{OFF}")
                        
                        # Call the LyricsEngine
                        engine.fetch_and_inject(
                            file_path=file_path,
                            artist=artist,
                            track=title,
                            album=album
                        )
                        injected += 1
                            
                except Exception as e:
                    print(f"{RED}[!] Error reading {file}: {e}{OFF}")
                    skipped += 1
                    
    print(f"\n{GREEN}[+] Retroactive Scan and Injection Completed!{OFF}")
    print(f"{CYAN}  - Total files analyzed: {processed}{OFF}")
    print(f"{GREEN}  - Injection attempts: {injected}{OFF}")
    print(f"{YELLOW}  - Skipped files (already tagged or missing data): {skipped}{OFF}\n")