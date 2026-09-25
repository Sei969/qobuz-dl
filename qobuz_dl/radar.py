import os
import configparser
import urllib.request
import xml.etree.ElementTree as ET
import questionary
from qobuz_dl.qopy import Client
from qobuz_dl.color import GREEN, YELLOW, RED, CYAN, OFF
from qobuz_dl.utils import read_config_file

def setup_client(config_path, config, section):
    """Initializes the Qobuz client reading from the config file."""
    app_id = config.get(section, 'app_id')
    secrets = config.get(section, 'secrets')
    auth_token = config.get(section, 'auth_token')
    email = config.get(section, 'email', fallback="") or None
    pwd = config.get(section, 'password', fallback="") or None

    api = Client(email, pwd, user_auth_token=auth_token, app_id=app_id, secrets=secrets)
    api.auth_token = auth_token
    return api

def get_or_save_rss_link(config_path, config, section):
    """Retrieves the RSS link or asks the user for it on first run."""
    if config.has_option(section, 'musicbutler_rss'):
        rss_link = config.get(section, 'musicbutler_rss').strip()
        if rss_link:
            return rss_link

    print(f"{YELLOW}[!] No RSS feed found.{OFF}")
    rss_link = questionary.text("Paste your private MusicButler RSS link here:").ask()
    
    if rss_link:
        config.set(section, 'musicbutler_rss', rss_link)
        with open(config_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        print(f"{GREEN}[+] Link permanently saved to config!{OFF}\n")
    
    return rss_link

def fetch_rss_releases(rss_url):
    """Downloads and parses the RSS/Atom feed ignoring XML namespaces."""
    print(f"{CYAN}[*] Syncing with MusicButler...{OFF}")
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        releases = []
        
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] 
            
            if tag in ['item', 'entry']:
                for child in elem.iter():
                    child_tag = child.tag.split('}')[-1]
                    if child_tag == 'title' and child.text:
                        releases.append(child.text.strip())
                        break
                        
        return releases
    except Exception as e:
        print(f"{RED}[!] Error reading RSS feed: {e}{OFF}")
        return []

def run_radar():
    """Main execution function for the radar command."""
    appdata_path = os.getenv('APPDATA')
    config_path = os.path.join(appdata_path, 'qobuz-dl', 'config.ini')
    
    config = configparser.ConfigParser()
    read_config_file(config, config_path)
    if not config.sections():
        print(f"{RED}[!] config.ini file not found at {config_path}{OFF}")
        return
        
    section = config.sections()[0]
    
    # 1. RSS Link Management
    rss_url = get_or_save_rss_link(config_path, config, section)
    if not rss_url:
        print(f"{RED}[!] Operation cancelled. No link provided.{OFF}")
        return

    # 2. Connect to Qobuz API
    try:
        api = setup_client(config_path, config, section)
    except Exception as e:
        print(f"{RED}[!] Connection error to Qobuz: {e}{OFF}")
        return

    # 3. Download and parse RSS
    releases = fetch_rss_releases(rss_url)
    
    if not releases:
        print(f"{YELLOW}[!] No new releases found in the feed.{OFF}")
        return
        
    print(f"{GREEN}[+] Found {len(releases)} new releases! Searching on Qobuz...{OFF}\n")

    # 4. Search on Qobuz and prepare the UI menu
    choices = []
    for release_title in releases:
        search_result = api.search_albums(release_title, limit=1)
        
        if search_result and "albums" in search_result and search_result["albums"]["items"]:
            album_data = search_result["albums"]["items"][0]
            album_id = album_data["id"]
            
            artist = album_data.get("artist", {}).get("name", "Unknown")
            title = album_data.get("title", "Unknown")
            display_name = f"{artist} - {title}"
            
            choices.append(questionary.Choice(title=display_name, value=album_id))
        else:
            print(f"{YELLOW}[!] Not found on Qobuz: {release_title}{OFF}")

    if not choices:
        print(f"{YELLOW}\n[!] None of the releases in the feed are currently available on Qobuz.{OFF}")
        return

    # 5. Interactive UI Menu
    print("\n")
    selected_album_ids = questionary.checkbox(
        "🎧 Select releases to add to Favorites (Space to select, Enter to confirm):",
        choices=choices
    ).ask()

    if not selected_album_ids:
        print(f"{YELLOW}[*] No albums selected. Exiting.{OFF}")
        return

    # 6. Add to Favorites
    print(f"\n{CYAN}[*] Adding {len(selected_album_ids)} albums to favorites...{OFF}")
    for album_id in selected_album_ids:
        try:
            api.add_favorite_album(album_id)
            print(f"{GREEN}  [+] Added: ID {album_id}{OFF}")
        except Exception as e:
            print(f"{RED}  [-] Error with ID {album_id}: {e}{OFF}")
            
    print(f"\n{GREEN}✅ Operation complete! You can now run qobuz-dl to download them.{OFF}")