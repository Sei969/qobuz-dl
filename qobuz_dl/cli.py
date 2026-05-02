import sys
import difflib
import string
import configparser
import logging
import glob
import os
import getpass
import hashlib
import signal

from qobuz_dl.bundle import Bundle
from qobuz_dl.color import GREEN, RED, YELLOW, OFF
from qobuz_dl.commands import qobuz_dl_args
from qobuz_dl.core import QobuzDL
from qobuz_dl.downloader import DEFAULT_FOLDER, DEFAULT_TRACK
from qobuz_dl.settings import QobuzDLSettings

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


def validate_config_formats(formats_to_check):
    """
    Scans the configuration format strings for unknown variables to prevent
    silent KeyErrors during the download process. Includes typo suggestions.
    """
    VALID_KEYS = {
        "artist", "album", "album_id", "album_url", "album_title", 
        "album_title_base", "album_artist", "album_genre", "album_composer", 
        "label", "copyright", "upc", "barcode", "release_date", "year", 
        "media_type", "format", "bit_depth", "sampling_rate", "album_version", 
        "version_tag", "disc_count", "track_count", "ExplicitFlag", "explicit", 
        "release_type", "tracktitle", "track_title", "track_title_base", 
        "track_id", "track_artist", "track_composer", "track_number", 
        "isrc", "version", "disc_number"
    }

    has_errors = False
    
    # Define color strings locally to ensure they print correctly in terminal
    C_RED = '\033[91m'
    C_YEL = '\033[93m'
    C_GRE = '\033[92m'
    C_OFF = '\033[0m'

    for config_name, format_string in formats_to_check.items():
        if not format_string:
            continue
            
        try:
            parsed_vars = [tup[1] for tup in string.Formatter().parse(str(format_string)) if tup[1] is not None]
            
            for var in parsed_vars:
                base_var = var.split(':')[0].split('!')[0]
                
                if base_var not in VALID_KEYS:
                    print(f"{C_YEL}[!] Config Warning: Unknown variable '{{{base_var}}}' detected in '{config_name}'.{C_OFF}")
                    
                    # --- NEW: 'Did you mean' logic using difflib ---
                    similar_keys = difflib.get_close_matches(base_var, VALID_KEYS, n=1, cutoff=0.6)
                    if similar_keys:
                        print(f"    {C_GRE}-> Did you mean '{{{similar_keys[0]}}}'?{C_OFF}")
                    # -----------------------------------------------
                    
                    print(f"    {C_RED}-> This will cause the entire format string to be discarded during download.{C_OFF}")
                    has_errors = True
                    
        except ValueError as e:
            print(f"{C_RED}[!] Config Error: Syntax error in '{config_name}' -> {e}{C_OFF}")
            has_errors = True

    if has_errors:
        print(f"\n{C_YEL}[*] Tip: Please check your config.ini file or your command line arguments and fix any typos before downloading.{C_OFF}\n")
        # Abort the process immediately
        sys.exit(1)


def _reset_config(config_file):
    logging.info(f"\n{YELLOW}--- QOBUZ-DL CONFIGURATION WIZARD (2026 Update) ---{OFF}")
    config = configparser.ConfigParser(interpolation=None)
    
    config["qobuz"] = {}
    
    email = input("Enter your Qobuz email:\n- ").strip()
    config["qobuz"]["email"] = email
    
    print(f"\n{YELLOW}[!] ATTENTION: Qobuz API blocked direct password login for 3rd party apps.{OFF}")
    print(f"{YELLOW}[!] You must use your browser Auth Token (F12 > Storage > Local Storage > localuser > token).{OFF}")
    
    auth_token = input("Paste your browser token here:\n- ").strip()
    
    config["qobuz"]["password"] = ""
    config["qobuz"]["auth_token"] = auth_token

    fetch_lyrics = input("Do you want to automatically download and inject lyrics? (yes/no) [Default: yes]\n- ").strip().lower()
    config["qobuz"]["fetch_lyrics"] = "false" if fetch_lyrics in ['no', 'n', 'false'] else "true"
    
    genius_token = ""
    if config["qobuz"]["fetch_lyrics"] == "true":
        print(f"{YELLOW}[!] To use Genius as a fallback, enter your API Token. Leave blank to only use LRCLIB (Free/No API).{OFF}")
        genius_token = input("Genius API Token:\n- ").strip()
    config["qobuz"]["genius_token"] = genius_token

    config["qobuz"]["directory"] = (
        input("Download folder (press Enter for 'Qobuz Downloads')\n- ")
        or "Qobuz Downloads"
    )
    
    # FIX: Use correct prompt and key for folder formatting
    config["qobuz"]["folder_format"] = (
        input(f"Folder format (press Enter for '{DEFAULT_FOLDER}')\n- ")
        or DEFAULT_FOLDER
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

    logging.info(f"{YELLOW}Getting tokens. Please wait...{OFF}")
    bundle = Bundle()
    config["qobuz"]["app_id"] = str(bundle.get_app_id())
    config["qobuz"]["secrets"] = ",".join(bundle.get_secrets().values())

    # Removed old folder_format override that caused custom format resets
    config["qobuz"]["track_format"] = "{track_number} - {track_title}"
    config["qobuz"]["fallback_folder_format"] = "{artist} - {album}"
    config["qobuz"]["smart_discography"] = "false"

    config["qobuz"]["no_album_artist_tag"] = "false"
    config["qobuz"]["no_album_title_tag"] = "false"
    config["qobuz"]["no_track_artist_tag"] = "false"
    config["qobuz"]["no_track_title_tag"] = "false"
    config["qobuz"]["no_release_date_tag"] = "false"
    config["qobuz"]["no_media_type_tag"] = "false"
    config["qobuz"]["no_genre_tag"] = "false"
    config["qobuz"]["no_track_number_tag"] = "false"
    config["qobuz"]["no_track_total_tag"] = "false"
    config["qobuz"]["no_disc_number_tag"] = "false"
    config["qobuz"]["no_disc_total_tag"] = "false"
    config["qobuz"]["no_composer_tag"] = "false"
    
    config["qobuz"]["no_explicit_tag"] = "false"
    config["qobuz"]["no_copyright_tag"] = "false"
    config["qobuz"]["no_label_tag"] = "false"
    
    config["qobuz"]["no_credits"] = "false"
    
    config["qobuz"]["no_upc_tag"] = "false"
    config["qobuz"]["no_isrc_tag"] = "false"
          
    config["qobuz"]["embedded_art_size"] = "600"
    config["qobuz"]["saved_art_size"] = "org"
    
    config["qobuz"]["multiple_disc_prefix"] = "CD"
    config["qobuz"]["multiple_disc_one_dir"] = "false"
    config["qobuz"]["multiple_disc_track_format"] = "{disc_number}.{track_number} - {track_title}"
    
    config["qobuz"]["max_workers"] = "3"
    config["qobuz"]["user_auth_token"] = ""
    
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
    def sigint_handler(sig, frame):
        print(f"\n\n\033[91m[!] Download forcibly interrupted by the user.\033[0m")
        print(f"\033[93mPartially downloaded files will be ignored or overwritten on the next run.\033[0m")
        try:
            _remove_leftovers(qobuz.directory)
        except Exception:
            pass
        sys.exit(1)
        
    signal.signal(signal.SIGINT, sigint_handler)

    try:
        if arguments.command == "dl":
            qobuz.download_list_of_urls(arguments.SOURCE)
        elif arguments.command in ("sync-playlist", "sp"):
            from qobuz_dl.sync_playlist import sync_playlist
            sync_playlist(
                qobuz,
                arguments.URL,
                qobuz.directory,  # <-- MODIFIED: Previously it was arguments.FOLDER
                auto_confirm=arguments.yes,
            )
        elif arguments.command == "lucky":
            query = " ".join(arguments.QUERY)
            qobuz.lucky_type = arguments.type
            qobuz.lucky_limit = arguments.number
            qobuz.lucky_mode(query)
        else:
            qobuz.interactive_limit = arguments.limit
            qobuz.interactive()

    except KeyboardInterrupt:
        pass
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

    # --- RADAR FEATURE (Standalone Intercept) ---
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "radar":
        from qobuz_dl.radar import run_radar
        
        try:
            run_radar()
        except KeyboardInterrupt:
            print("\n\n\033[91m[!] Radar manually interrupted by the user (CTRL+C).\033[0m")
        sys.exit(0)
    # --------------------------------------------

    config = configparser.ConfigParser(interpolation=None)
    config.read(CONFIG_FILE)

    try:
        section = "qobuz" if config.has_section("qobuz") else "DEFAULT"
        
        email = config.get(section, "email")
        token = config.get(section, "auth_token", fallback="")
        password = token if token else config.get(section, "password")
        
        fetch_lyrics = config.getboolean(section, "fetch_lyrics", fallback=False)
        genius_token = config.get(section, "genius_token", fallback=None)
        
        # --- FIX: Backward compatibility for default_folder ---
        directory_val = config.get(section, "directory", fallback=None)
        if directory_val is not None:
            default_folder = directory_val
        else:
            legacy_val = config.get(section, "default_folder", fallback=None)
            if legacy_val is not None:
                # If the legacy key is used, accept it but print a yellow warning
                print(f"\033[93m[!] Notice: 'default_folder' in config.ini is deprecated. Please rename it to 'directory' for future updates.\033[0m")
                default_folder = legacy_val
            else:
                default_folder = "Qobuz Downloads"
        # ------------------------------------------------------
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
        
        if getattr(arguments, 'no_lyrics', False):
            fetch_lyrics = False
            
        force_english = not getattr(arguments, 'native_lang', False)
        no_credits_flag = getattr(arguments, 'no_credits', False) 
        
    except (configparser.Error, KeyError) as error:
        arguments = qobuz_dl_args().parse_args()
        if not arguments.reset:
            # FIX: Define ANSI codes locally to bypass UnboundLocalError
            RED_C = '\033[91m'
            YELLOW_C = '\033[93m'
            OFF_C = '\033[0m'
            sys.exit(
                f"{RED_C}Invalid or corrupted configuration ({error}).\n{OFF_C}"
                f"{YELLOW_C}Run 'python -m qobuz_dl -r' to fix this.{OFF_C}"
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

    # --- NEW DB SYNC FEATURE (Lightweight Mode) ---
    if getattr(arguments, 'sync_db', None):
        from qobuz_dl.sync import sync_database
        from qobuz_dl.qopy import Client
                
        # Initialize a lightweight API client for Reverse Lookup (bypassing the heavy downloader)
        sync_client = Client(email, password, app_id, secrets, user_auth_token=token, force_english=force_english)
        
        # Path management
        sync_dir = default_folder if arguments.sync_db == "DEFAULT" else arguments.sync_db
        
        if os.name == "nt":
            sync_dir = os.path.abspath(sync_dir)
            if not sync_dir.startswith("\\\\?\\"):
                sync_dir = "\\\\?\\" + sync_dir
                
        sync_database(sync_dir, QOBUZ_DB, sync_client)
        sys.exit(f"\n{GREEN}Database synchronization finished successfully.{OFF}")
    # ----------------------------------------------

    # --- RETRO LYRICS FEATURE (Standalone Mode) ---
    # Intercept the command here before QobuzDLSettings looks for 'directory', which would crash the program
    if arguments.command == "lyrics":
        from qobuz_dl.retro_tagger import inject_lyrics_retroactively
        
        target_dir = arguments.DIR
        if os.name == "nt":
            target_dir = os.path.abspath(target_dir)
            if not target_dir.startswith("\\\\?\\"):
                target_dir = "\\\\?\\" + target_dir
                
        try:
            inject_lyrics_retroactively(target_dir, genius_token=genius_token)
        except KeyboardInterrupt:
            print("\n\n\033[91m[!] Operation manually interrupted by the user (CTRL+C).\033[0m")
            print("\033[93mAlready processed files are safe. Exiting...\033[0m")
        sys.exit(0)
    # ----------------------------------------------

    directory_to_use = arguments.directory if hasattr(arguments, 'directory') and arguments.directory else default_folder
    directory_to_use = os.path.expanduser(directory_to_use)

    # --- WINDOWS LONG PATH BYPASS ---
    if os.name == "nt":
        directory_to_use = os.path.abspath(directory_to_use)
        if not directory_to_use.startswith("\\\\?\\"):
            directory_to_use = "\\\\?\\" + directory_to_use
    # --------------------------------

    settings = QobuzDLSettings.from_arguments_configparser(arguments, config)
    
    # Execute the Pre-flight Config Check
    # --- PRE-FLIGHT CONFIG CHECK ---
    formats_to_validate = {
        "folder_format": arguments.folder_format or folder_format,
        "track_format": arguments.track_format or track_format,
        "fallback_folder_format": config.get(section, "fallback_folder_format", fallback="{artist} - {album}"),
        "multiple_disc_track_format": config.get(section, "multiple_disc_track_format", fallback="{disc_number}.{track_number} - {track_title}")
    }
    validate_config_formats(formats_to_validate)
    # -------------------------------

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
        fetch_lyrics=fetch_lyrics,
        genius_token=genius_token,
        force_english=force_english,
        no_credits=no_credits_flag,
        settings=settings,
    )
    
    qobuz.initialize_client(email, password, app_id, secrets)

    _handle_commands(qobuz, arguments)


if __name__ == "__main__":
    main()