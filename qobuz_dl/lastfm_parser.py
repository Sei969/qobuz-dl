import requests
from bs4 import BeautifulSoup
from qobuz_dl.color import OFF, GREEN, RED, YELLOW, CYAN

def fetch_lastfm_playlist(url: str) -> list:
    """
    Fetches a Last.fm playlist URL and extracts the tracks.
    Returns a list of dictionaries: [{'artist': '...', 'title': '...'}]
    """
    print(f"{CYAN}[*] Analyzing Last.fm playlist...{OFF}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"{RED}[!] Failed to connect to Last.fm: {e}{OFF}")
        return []

    # Parse the HTML content
    soup = BeautifulSoup(response.text, 'html.parser')
    tracks = []
    
    # Locate all track rows in the playlist table
    # Last.fm typically uses 'chartlist-row' for its track lists
    rows = soup.find_all('tr', class_='chartlist-row')
    
    for row in rows:
        artist_tag = row.find('td', class_='chartlist-artist')
        title_tag = row.find('td', class_='chartlist-name')
        
        if artist_tag and title_tag:
            # Clean up the extracted text
            artist = artist_tag.get_text(strip=True)
            title = title_tag.get_text(strip=True)
            tracks.append({"artist": artist, "title": title})
            
    if not tracks:
        print(f"{YELLOW}[!] No tracks found. The playlist might be empty or Last.fm changed their layout.{OFF}")
    else:
        print(f"{GREEN}[+] Successfully extracted {len(tracks)} tracks from Last.fm!{OFF}")
        
    return tracks