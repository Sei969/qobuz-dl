import configparser
import logging
import glob
import os
import sys
import getpass

from qobuz_dl.color import GREEN, RED, YELLOW, OFF
from qobuz_dl.commands import qobuz_dl_args
from qobuz_dl.core import QobuzDL
from qobuz_dl.downloader import DEFAULT_FOLDER, DEFAULT_TRACK

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)

if os.name == "nt":
    OS_CONFIG = os.environ.get("APPDATA")
else:
    OS_CONFIG = os.path.join(os.environ["HOME"], ".config")

CONFIG_PATH = os.path.join(OS_CONFIG, "qobuz-dl")
CONFIG_FILE = os.path.join(CONFIG_PATH, "config.ini")
QOBUZ_DB = os.path.join(CONFIG_PATH, "qobuz_dl.db")


def _reset_config(config_file):
    logging.info(f"\n{YELLOW}--- QOBUZ-DL CONFIGURATION WIZARD (2026 Update) ---{OFF}")
    config = configparser.ConfigParser()
    
    # Create specific [qobuz] section to avoid 'corrupted' errors
    config["qobuz"] = {}
    
    email = input("Enter your Qobuz email:\n- ").strip()
    config["qobuz"]["email"] = email
    
    print(f"{YELLOW}[!] If you prefer to use the browser Auth Token, leave the password blank.{OFF}")
    password = getpass.getpass("Enter your password (it will be hidden):\n- ").strip()
    config["qobuz"]["password"] = password
    
    auth_token = ""
    if not password:
        auth_token = input("Paste your browser user_auth_token here:\n- ").strip()
    config["qobuz"]["auth_token"] = auth_token

    # --- NEW: LYRICS CONFIGURATION ---
    fetch_lyrics = input("Do you want to automatically download and inject lyrics? (yes/no) [Default: yes]\n- ").strip().lower()
    config["qobuz"]["fetch_lyrics"] = "false" if fetch_lyrics in ['no', 'n', 'false'] else "true"
    
    genius_token = ""
    if config["qobuz"]["fetch_lyrics"] == "true":
        print(f"{YELLOW}[!] To use Genius as a fallback, enter your API Token. Leave blank to only use LRCLIB (Free/No API).{OFF}")
        genius_token = input("Genius API Token:\n- ").strip()
    config["qobuz"]["genius_token"] = genius_token
    # -----------------------------------

    config["qobuz"]["default_folder"] = (
        input("Download folder (press Enter for '.' current directory)\n- ")
        or "."
    )
    config["qobuz"]["default_quality"] = (
        input("Download quality (5:MP3, 6:FLAC, 7:24b<96, 27:24b>96) [Default 27]\n- ")
        or "27"
    )
    
    config["qobuz"]["default_limit"] = "500"
    config["qobuz"]["no_m3u"] = "false"
    config["qobuz"]["albums_only"] = "false"
    config["qobuz"]["no_fallback"] = "false"
    config["qobuz"]["og_cover"] = "true"
    config["qobuz"]["embed_art"] = "true"
    config["qobuz"]["no_cover"] = "false"
    config["qobuz"]["no_database"] = "false"
    config["qobuz"]["app_id"] = "470123565"
    config["qobuz"]["secrets"] = "96924823297a47568581f3d537f14b62"
    config["qobuz"]["folder_format"] = "{artist} - {album}"
    config["qobuz"]["track_format"] = "{tracknumber} {tracktitle}"
    config["qobuz"]["smart_discography"] = "false"

    with open(config_file, "w") as configfile:
        config.write(configfile)
        
    logging.info(f"\n{GREEN}[+] Configuration successfully saved in {config_file}!{OFF}")
    

def _remove_leftovers(directory):
    directory = os.path.join(directory, "**", ".*.tmp")
    for i in glob.glob(directory, recursive=True):
        try:
            os.remove(i)
        except:  # noqa
            pass


def _handle_commands(qobuz, arguments):
    try:
        if arguments.command == "dl":
            qobuz.download_list_of_urls(arguments.SOURCE)
        elif arguments.command == "lucky":
            query = " ".join(arguments.QUERY)
            qobuz.lucky_type = arguments.type
            qobuz.lucky_limit = arguments.number
            qobuz.lucky_mode(query)
        else:
            qobuz.interactive_limit = arguments.limit
            qobuz.interactive()

    except KeyboardInterrupt:
        logging.info(
            f"\n{RED}Interrupted by user.{OFF}\n{YELLOW}Already downloaded files will be skipped on the next run.{OFF}"
        )

    finally:
        _remove_leftovers(qobuz.directory)


def _initial_checks():
    if not os.path.isdir(CONFIG_PATH) or not os.path.isfile(CONFIG_FILE):
        os.makedirs(CONFIG_PATH, exist_ok=True)
        _reset_config(CONFIG_FILE)

    if len(sys.argv) < 2:
        sys.exit(qobuz_dl_args().print_help())


def main():
    _initial_checks()

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    # TICKET FIX: Reading from [qobuz] section instead of [DEFAULT]
    # We use .get() with fallback to prevent crashes if rows are missing
    try:
        section = "qobuz" if config.has_section("qobuz") else "DEFAULT"
        
        email = config.get(section, "email")
        token = config.get(section, "auth_token", fallback="")
        password = token if token else config.get(section, "password")
        
        # --- READ LYRICS SETTINGS ---
        fetch_lyrics = config.getboolean(section, "fetch_lyrics", fallback=False)
        genius_token = config.get(section, "genius_token", fallback=None)
        
        default_folder = config.get(section, "default_folder")
        default_limit = config.get(section, "default_limit")
        default_quality = config.get(section, "default_quality")
        
        no_m3u = config.getboolean(section, "no_m3u", fallback=False)
        albums_only = config.getboolean(section, "albums_only", fallback=False)
        no_fallback = config.getboolean(section, "no_fallback", fallback=False)
        og_cover = config.getboolean(section, "og_cover", fallback=True)
        embed_art = config.getboolean(section, "embed_art", fallback=True)
        no_cover = config.getboolean(section, "no_cover", fallback=False)
        no_database = config.getboolean(section, "no_database", fallback=False)
        
        app_id = config.get(section, "app_id")
        secrets = [s for s in config.get(section, "secrets").split(",") if s]
        
        smart_discography = config.getboolean(section, "smart_discography", fallback=False)
        folder_format = config.get(section, "folder_format", fallback=DEFAULT_FOLDER)
        track_format = config.get(section, "track_format", fallback=DEFAULT_TRACK)

        arguments = qobuz_dl_args(
            default_quality, default_limit, default_folder
        ).parse_args()
        
        # --- OVERRIDE VIA CLI ARGS ---
        if getattr(arguments, 'no_lyrics', False):
            fetch_lyrics = False
            
        force_english = not getattr(arguments, 'native_lang', False)
        no_credits_flag = getattr(arguments, 'no_credits', False) # <-- NEW FLAG CAPTURE
        # -----------------------------
        
    except (configparser.Error, KeyError) as error:
        arguments = qobuz_dl_args().parse_args()
        if not arguments.reset:
            sys.exit(
                f"{RED}Invalid or corrupted configuration ({error}).\n{OFF}"
                f"{YELLOW}Run 'python -m qobuz_dl -r' to fix this.{OFF}"
            )

    if arguments.reset:
        sys.exit(_reset_config(CONFIG_FILE))

    if arguments.show_config:
        print(f"Configuration: {CONFIG_FILE}\nDatabase: {QOBUZ_DB}\n---")
        with open(CONFIG_FILE, "r") as f:
            print(f.read())
        sys.exit()

    if arguments.purge:
        try:
            os.remove(QOBUZ_DB)
        except FileNotFoundError:
            pass
        sys.exit(f"{GREEN}Database has been purged.{OFF}")

    # FIX: Resolved hardcoded path issue to support cross-platform usage
    directory_to_use = arguments.directory if hasattr(arguments, 'directory') and arguments.directory else default_folder

    qobuz = QobuzDL(
        directory_to_use,
        arguments.quality,
        arguments.embed_art or embed_art,
        ignore_singles_eps=arguments.albums_only or albums_only,
        no_m3u_for_playlists=arguments.no_m3u or no_m3u,
        quality_fallback=not arguments.no_fallback or not no_fallback,
        cover_og_quality=arguments.og_cover or og_cover,
        no_cover=arguments.no_cover or no_cover,
        downloads_db=None if no_database or arguments.no_db else QOBUZ_DB,
        folder_format=arguments.folder_format or folder_format,
        track_format=arguments.track_format or track_format,
        smart_discography=arguments.smart_discography or smart_discography,
        # --- ACTIVATE LYRICS ENGINE & METADATA OVERRIDES ---
        fetch_lyrics=fetch_lyrics,
        genius_token=genius_token,
        force_english=force_english,
        no_credits=no_credits_flag # <-- NEW PARAMETER PASSED TO CORE
    )
    
    qobuz.initialize_client(email, password, app_id, secrets)

    _handle_commands(qobuz, arguments)


if __name__ == "__main__":
    main()