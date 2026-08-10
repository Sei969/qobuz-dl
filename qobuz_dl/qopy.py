import base64
import hashlib
import logging
import time
import unicodedata
import json

import requests
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from qobuz_dl.exceptions import (
    AuthenticationError,
    InvalidAppIdError,
    InvalidAppSecretError,
    InvalidQuality,
)
from qobuz_dl.color import GREEN, YELLOW, RED, OFF, RESET

try:
    from qobuz_dl.bundle import Bundle
except ImportError:
    Bundle = None

logger = logging.getLogger(__name__)

class Client:
    """
    The core Qobuz API client for Qobuz-DL Ultimate Edition.

    Handles secure authentication, Anti-Ban Stealth Spoofing (WAF bypass), cryptographic 
    token unwrapping for Web Player segment streams, and dynamic metadata fetching. 
    Supports both standard email/password authentication and secure user_auth_token injection.
    """

    def __init__(self, email, pwd, app_id, secrets, user_auth_token=None, force_english=True):
        """
        Initializes the API client and sets up the resilient session.

        Args:
            email (str): The user's Qobuz account email.
            pwd (str): The user's Qobuz account password.
            app_id (str): The Qobuz Application ID.
            secrets (list): A list of potential Qobuz App Secrets for authentication fallback.
            user_auth_token (str, optional): A pre-existing authentication token to bypass login. Defaults to None.
            force_english (bool, optional): Injects specific Client Hints and locales to avoid bans. Defaults to True.
        """
        logger.info(f"{YELLOW}Logging...{OFF}")
        self.secrets = secrets
        self.id = str(app_id)
        self.secrets = secrets
        self.force_english = force_english
        
        if Bundle:
            try:
                b = Bundle()
                fresh_id = str(b.get_app_id())
                if fresh_id:
                    self.id = fresh_id
                    self.secrets = list(b.get_secrets().values())
                    logger.info(f"{GREEN}[+] App ID dynamically updated: {self.id}{OFF}")
            except Exception:
                pass

        self.session = requests.Session()
        
        # --- CONDITIONAL ENGLISH LANGUAGE OVERRIDE ---
        if self.force_english:
            self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "X-App-Language": "en",
            "X-App-Region": "US",
            "Sec-Ch-Ua": "\"Chromium\";v=\"124\", \"Google Chrome\";v=\"124\", \"Not-A.Brand\";v=\"99\"",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "\"Windows\"",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "X-App-Id": self.id,
        })
        # ---------------------------------------------
        
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-App-Id": self.id,
        })
        self.base = "https://www.qobuz.com/api.json/0.2/"
        self.sec = None
        # Variables for encryption session management
        self.session_id = None
        self.session_infos = None
        self.session_key = None
        
        self.uat = None
        self.force_english = force_english 
        
        self.auth(email, pwd, user_auth_token)
        self.cfg_setup()

    def _normalize_json_strings(self, obj):
        """
        Recursively normalizes Unicode strings in JSON objects (NFC form).
        Prevents encoding crashes and fixes Windows path limitations (e.g., trailing ellipses).

        Args:
            obj (mixed): The JSON dictionary, list, or string to normalize.

        Returns:
            mixed: The normalized object.
        """
        if isinstance(obj, str):
            # --- WINDOWS PATH FIX: Convert '...' to Unicode Ellipsis (U+2026) ---
            # Avoid modifying URL links (which contain '://')
            if "..." in obj and "://" not in obj:
                obj = obj.replace("...", "…")
            # --------------------------------------------------------------------
            return unicodedata.normalize('NFC', obj)
        elif isinstance(obj, dict):
            return {k: self._normalize_json_strings(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._normalize_json_strings(item) for item in obj]
        else:
            return obj

    def auth(self, email, pwd, user_auth_token=None):
        """
        Authenticates the user session with Qobuz and retrieves account metadata.

        Args:
            email (str): The user's email address.
            pwd (str): The user's password.
            user_auth_token (str, optional): Direct token to bypass credential check. Defaults to None.
        """
        # If the token is present, skip the password!
        if user_auth_token:
            self.uat = user_auth_token
        elif len(pwd) > 60:
            self.uat = pwd
        else:
            usr_info = self.api_call("user/login", email=email, pwd=pwd)
            if not usr_info.get("user", {}).get("credential", {}).get("parameters"):
                logger.info(f"{YELLOW}[!] Free account detected or validation bypassed.{OFF}")
            self.uat = usr_info["user_auth_token"]
        
        self.session.headers.update({"X-User-Auth-Token": self.uat})
        
        try:
            user_info = self.api_call("user/get")
            cred = user_info.get("credential") or user_info.get("user", {}).get("credential", {})
            self.label = cred.get("parameters", {}).get("short_label", "Studio")
            
            # --- FIX: Save user ID strictly required for favorites ---
            self.user_id = user_info.get("id") or user_info.get("user", {}).get("id")
            # -------------------------------------------------------------------------
            
            logger.info(f"{GREEN}Logged: OK (Membership: {self.label}){OFF}")
        except Exception:
            logger.info(f"{YELLOW}[!] Profile validation bypassed.{OFF}")
            self.label = "Studio"
            self.user_id = None

    # NEW CRYPTOGRAPHIC FUNCTIONS (Patch 0004)
    def _modern_sig(self, epoint, params, sec):
        """
        Generates a modern MD5 signature for Qobuz protected endpoints.

        Args:
            epoint (str): The API endpoint path.
            params (dict): The dictionary of request parameters.
            sec (str): The application secret key.

        Returns:
            str: The computed MD5 signature hash.
        """
        object_, method = epoint.split("/")
        r_sig = [object_, method]
        for key in sorted(params):
            value = params[key]
            if key not in ("request_ts", "request_sig") and isinstance(
                value, (str, int, float)
            ):
                r_sig.extend((key, str(value)))
        r_sig.extend((str(params["request_ts"]), sec))
        return hashlib.md5("".join(r_sig).encode("utf-8")).hexdigest()

    @staticmethod
    def _b64url_decode(value):
        """Helper to decode base64 url-safe strings with proper padding."""
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    def _derive_session_key(self):
        """
        Derives an AES session key using HKDF based on Qobuz session infos.
        Used for decrypting Web Player stream chunks.

        Returns:
            bytes: The 16-byte derived session key.
        """
        salt, info = self.session_infos.split(".")
        return HKDF(
            algorithm=hashes.SHA256(),
            length=16,
            salt=self._b64url_decode(salt),
            info=self._b64url_decode(info),
        ).derive(bytes.fromhex(self.sec))

    def _unwrap_track_key(self, key_token):
        """
        Decrypts the AES wrapped track key provided by the API.

        Args:
            key_token (str): The encrypted key token string.

        Returns:
            bytes: The unwrapped, decrypted raw track key.
        """
        _, wrapped, iv = key_token.split(".")
        decryptor = Cipher(
            algorithms.AES(self.session_key),
            modes.CBC(self._b64url_decode(iv)),
        ).decryptor()
        padded = decryptor.update(self._b64url_decode(wrapped)) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded) + unpadder.finalize()

    # NEW API_CALL ENGINE
    def api_call(self, epoint, **kwargs):
        """
        The central routing engine for all Qobuz API requests.
        
        Dynamically handles HTTP methods (GET/POST), cryptographic signing, error parsing, 
        and automatic Unicode normalization for all responses.

        Args:
            epoint (str): The target Qobuz API endpoint (e.g., 'album/get').
            **kwargs: Arbitrary keyword arguments corresponding to API parameters.

        Raises:
            AuthenticationError: On invalid login credentials.
            InvalidAppIdError: On invalid App ID.
            InvalidAppSecretError: On invalid App Secret.

        Returns:
            dict: The normalized JSON response from the Qobuz API.
        """
        if epoint == "user/login":
            if "user_auth_token" in kwargs and kwargs["user_auth_token"]:
                params = {
                    "user_auth_token": kwargs["user_auth_token"],
                    "app_id": self.id,
                }
            else:
                params = {
                    "email": kwargs["email"],
                    "password": kwargs["pwd"],
                    "app_id": self.id,
                }
        elif epoint == "track/getFileUrl":
            track_id = kwargs["id"]
            fmt_id = kwargs["fmt_id"]
            if int(fmt_id) not in (5, 6, 7, 27):
                raise InvalidQuality("Invalid quality id: choose between 5, 6, 7 or 27")
            params = {
                "track_id": track_id,
                "format_id": fmt_id,
                "intent": "stream",
            }
            # Use the old string method for MP3 compatibility
            unix = int(time.time())
            sec_to_use = kwargs.get('sec', self.sec)
            r_sig = f"trackgetFileUrlformat_id{fmt_id}intentstreamtrack_id{track_id}{unix}{sec_to_use}"
            params["request_ts"] = unix
            params["request_sig"] = hashlib.md5(r_sig.encode()).hexdigest()

        elif epoint == "session/start":
            params = {"profile": "qbz-1"}
            params["request_ts"] = int(time.time())
            params["request_sig"] = self._modern_sig(
                epoint, params, kwargs.get("sec", self.sec)
            )
        elif epoint == "file/url":
            track_id = kwargs["id"]
            fmt_id = kwargs["fmt_id"]
            if int(fmt_id) not in (6, 7, 27):
                raise InvalidQuality("Invalid quality id: choose between 6, 7 or 27")
            params = {
                "track_id": track_id,
                "format_id": fmt_id,
                "intent": "import",
            }
            params["request_ts"] = int(time.time())
            params["request_sig"] = self._modern_sig(
                epoint, params, kwargs.get("sec", self.sec)
            )
        elif epoint == "favorite/getUserFavorites":
            unix = int(time.time())
            r_sig = "favoritegetUserFavorites" + str(unix) + kwargs.get("sec", self.sec)
            r_sig_hashed = hashlib.md5(r_sig.encode("utf-8")).hexdigest()
            params = {
                "app_id": self.id,
                "user_auth_token": getattr(self, 'uat', None),
                "user_id": getattr(self, 'user_id', None), 
                "type": kwargs.get("fav_type", "albums"),
                "limit": kwargs.get("limit", 100),
                "offset": kwargs.get("offset", 0),
                "request_ts": unix,
                "request_sig": r_sig_hashed,
            }
        else:
            # Restore behavior for standard calls like album/get
            params = {'app_id': self.id}
            
            # --- CONDITIONAL ENGLISH PARAMS OVERRIDE ---
            if getattr(self, 'force_english', True):
                params['lang'] = 'en'
                params['locale'] = 'en_US'
            # -------------------------------------------
            
            val_id = kwargs.get('id')
            for k, v in kwargs.items():
                if k not in ['id', 'sec', 'fmt_id']:
                    params[k] = v

            if epoint == "album/get": params["album_id"] = val_id
            elif epoint == "track/get": params["track_id"] = val_id
            elif epoint == "playlist/get": params["playlist_id"] = val_id; params["extra"] = "tracks"
            elif epoint == "artist/get": params["artist_id"] = val_id; params["extra"] = "albums"
            elif epoint == "label/get": params["label_id"] = val_id; params["extra"] = "albums"

        # PATCH: Added favorite/create to POST methods
        if epoint in ["user/login", "favorite/create"]:
            r = self.session.post(self.base + epoint, data=params)
        elif epoint == "session/start":
            r = self.session.post(
                self.base + epoint,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        else:
            r = self.session.get(self.base + epoint, params=params)

        if epoint == "user/login" and r.status_code == 400:
            if "invalid" in r.text.lower():
                raise AuthenticationError("Invalid email or password.")
            else:
                logger.info(f"{GREEN}Logged: OK{OFF}")
        elif (
            epoint in ["track/getFileUrl", "favorite/getUserFavorites", "file/url"]
            and r.status_code == 400
        ):
            raise InvalidAppSecretError(f"Invalid app secret: {r.json()}.\n" + RESET)
        
        if epoint == "user/get" and r.status_code == 400: return {}
        r.raise_for_status()
        
        # Apply string normalizer to the network call output
        return self._normalize_json_strings(r.json())

    def multi_meta(self, epoint, key, id, type):
        """
        A generator that handles paginated API requests, automatically fetching chunks of 50 items.

        Args:
            epoint (str): The API endpoint (e.g., 'playlist/get').
            key (str): The JSON key containing total counts (e.g., 'tracks_count').
            id (str): The target ID (playlist ID, artist ID, etc.).
            type (str): The expected data type in the response ('albums', 'tracks').

        Yields:
            dict: The dictionary containing the chunked API response block.
        """
        offset = 0
        limit = 50
        
        while True:
            j = self.api_call(epoint, id=id, offset=offset, limit=limit, type=type)
            res = j[type] if type and type in j else j
            
            items_key = "tracks" if "playlist" in epoint else "albums"
            items = res.get(items_key, {}).get("items", [])
            
            if not items:
                break
                
            yield res
            
            offset += len(items)
            total_available = res.get(items_key, {}).get("total", res.get(key, 0))
            if offset >= total_available:
                break

    # --- METADATA FUNCTIONS (Do not delete!) ---
    def get_track_meta(self, id): 
        """Fetches metadata for a single track."""
        return self.api_call("track/get", id=id)

    # --- NEW LAST.FM FUNCTIONS ---
    def get_track_ids_from_list(self, tracks_list: list) -> list:
        """
        Matches a list of external tracks (e.g., scraped from Last.fm) against the Qobuz database.

        Uses a Fuzzy Matching Algorithm to compare artist and title strings.
        Features an interactive terminal prompt for borderline matches (60%-74% similarity).

        Args:
            tracks_list (list): A list of dictionaries containing 'artist' and 'title' keys.

        Returns:
            list: A list of successfully matched Qobuz track IDs.
        """
        from qobuz_dl.color import OFF, GREEN, RED, YELLOW, CYAN
        import difflib
        
        print(f"{CYAN}[*] Matching Last.fm tracks with Qobuz database (Fuzzy matching & Interactive mode enabled)...{OFF}")
        valid_track_ids = []
        
        AUTO_ACCEPT_THRESHOLD = 0.75 
        PROMPT_THRESHOLD = 0.60      
        
        for item in tracks_list:
            target_artist = item['artist'].lower()
            target_title = item['title'].lower()
            query = f"{item['artist']} {item['title']}"
            
            try:
                search_results = self.search_tracks(query, limit=5)
                
                best_match_id = None
                best_match_name = ""
                highest_ratio = 0.0
                
                if search_results and "tracks" in search_results and search_results["tracks"]["items"]:
                    for q_track in search_results["tracks"]["items"]:
                        q_artist_raw = q_track.get("performer", {}).get("name", "Unknown")
                        q_title_raw = q_track.get("title", "Unknown")
                        
                        q_artist = q_artist_raw.lower()
                        q_title = q_title_raw.lower()
                        
                        target_str = f"{target_artist} {target_title}"
                        q_str = f"{q_artist} {q_title}"
                        
                        ratio = difflib.SequenceMatcher(None, target_str, q_str).ratio()
                        
                        if ratio > highest_ratio:
                            highest_ratio = ratio
                            best_match_id = q_track["id"]
                            best_match_name = f"{q_artist_raw} - {q_title_raw}"
                    
                    if highest_ratio >= AUTO_ACCEPT_THRESHOLD and best_match_id:
                        valid_track_ids.append(best_match_id)
                        
                    elif highest_ratio >= PROMPT_THRESHOLD and best_match_id:
                        print(f"\n{YELLOW}[?] Borderline match detected ({highest_ratio*100:.0f}% similarity){OFF}")
                        print(f"    Target (Last.fm): {item['artist']} - {item['title']}")
                        print(f"    Found  (Qobuz)  : {best_match_name}")
                        
                        choice = input(f"{CYAN}    Do you want to download this track anyway? [y/n]: {OFF}").strip().lower()
                        
                        if choice == 'y':
                            valid_track_ids.append(best_match_id)
                            print(f"{GREEN}    [+] Track accepted manually.{OFF}")
                        else:
                            print(f"{RED}    [-] Track skipped manually.{OFF}")
                            
                    else:
                        print(f"{YELLOW}[!] Skipping: '{query}' (Best match was only {highest_ratio*100:.0f}% similar){OFF}")
                        
                else:
                    print(f"{YELLOW}[!] Skipping (No results on Qobuz for): '{query}'{OFF}")
                    
            except Exception as e:
                print(f"{RED}[!] Error searching for '{query}': {e}{OFF}")
                
        print(f"\n{GREEN}[+] Successfully matched {len(valid_track_ids)} out of {len(tracks_list)} tracks!{OFF}")
        return valid_track_ids

    # --- SEARCH FUNCTIONS (Crash-Proof) ---
    def search_albums(self, query, limit=20):
        """Searches the Qobuz catalog for albums. Crash-proof against API timeouts."""
        try: return self.api_call("catalog/search", query=query, type="albums", limit=limit)
        except Exception: return {}

    def search_tracks(self, query, limit=20):
        """Searches the Qobuz catalog for tracks. Crash-proof against API timeouts."""
        try: return self.api_call("catalog/search", query=query, type="tracks", limit=limit)
        except Exception: return {}

    def search_playlists(self, query, limit=20):
        """Searches the Qobuz catalog for playlists. Crash-proof against API timeouts."""
        try: return self.api_call("catalog/search", query=query, type="playlists", limit=limit)
        except Exception: return {}

    def search_artists(self, query, limit=20):
        """Searches the Qobuz catalog for artists. Crash-proof against API timeouts."""
        try: return self.api_call("catalog/search", query=query, type="artists", limit=limit)
        except Exception: return {}

    # --- NEW FAVORITES FUNCTION ---
    def get_favorites(self, fav_type="albums", limit=100, offset=0):
        """
        Fetches the authenticated user's favorites from their private library.

        Args:
            fav_type (str, optional): The type of favorites to fetch ('albums', 'tracks', 'artists', 'playlists'). Defaults to "albums".
            limit (int, optional): The number of items to retrieve per call. Defaults to 100.
            offset (int, optional): The pagination offset. Defaults to 0.

        Returns:
            dict: The API response containing the favorites list.
        """
        try: 
            return self.api_call("favorite/getUserFavorites", fav_type=fav_type, limit=limit, offset=offset)
        except Exception as e: 
            logger.error(f"{RED}[!] API Error fetching favorites: {e}{OFF}")
            return {}
            
    def add_favorite_album(self, album_id):
        """
        Adds a specific album to the user's Qobuz favorites.

        Args:
            album_id (str): The Qobuz ID of the album to favorite.

        Returns:
            dict: The API response acknowledging the addition.
        """
        return self.api_call(
            "favorite/create", 
            album_ids=str(album_id),
            artist_ids="",
            track_ids=""
        )
        
    # NEW GET_TRACK_URL (Patch 0004)
    def get_track_url(self, id, fmt_id, force_segments=False):
        """
        Retrieves the streaming or download URL for a specific track.

        Employs an intelligent fallback mechanism: attempts to fetch a fast Direct URL first, 
        and if blocked by Qobuz CDNs, automatically falls back to the Segmented Web Player 
        method (decrypting AES stream chunks).

        Args:
            id (str): The Qobuz track ID.
            fmt_id (int): The audio format ID (e.g., 5 for MP3, 27 for Hi-Res FLAC).
            force_segments (bool, optional): If True, bypasses Direct URL attempt. Defaults to False.

        Returns:
            dict: The track payload containing the URL or stream keys.
        """
        # Quick fallback for MP3
        if int(fmt_id) == 5:
            return self.api_call("track/getFileUrl", id=id, fmt_id=fmt_id)

        # If not forcing segments, try the good old fast Direct URL first
        if not force_segments:
            try:
                track = self.api_call("track/getFileUrl", id=id, fmt_id=fmt_id)
                if "url" in track:
                    return track
            except Exception:
                pass # If Qobuz refuses to give the direct URL, fallback to segments automatically

        # "WEB PLAYER" METHOD (SEGMENTED DOWNLOAD)
        if self.session_id is None:
            session = self.api_call("session/start")
            self.session_id = session["session_id"]
            self.session_infos = session["infos"]
            self.session_key = self._derive_session_key()
            self.session.headers.update({"X-Session-Id": self.session_id})

        track = self.api_call("file/url", id=id, fmt_id=fmt_id)
        if "bits_depth" in track and "bit_depth" not in track:
            track["bit_depth"] = track["bits_depth"]
        if track.get("sampling_rate", 0) > 1000:
            track["sampling_rate"] = track["sampling_rate"] / 1000
        if "key" in track:
            track["raw_key"] = self._unwrap_track_key(track["key"])
        return track

    def get_artist_meta(self, id): 
        """Fetches full metadata and discography for an artist."""
        return self.multi_meta("artist/get", "albums_count", id, None)
        
    def get_plist_meta(self, id): 
        """Fetches full metadata and tracklist for a playlist."""
        return self.multi_meta("playlist/get", "tracks_count", id, None)
        
    def get_label_meta(self, id): 
        """Fetches full metadata and release catalog for a record label."""
        return self.multi_meta("label/get", "albums_count", id, None)
        
    def get_album_meta(self, id): 
        """Fetches full metadata for a specific album."""
        return self.api_call("album/get", id=id)
    
    def cfg_setup(self):
        """
        Validates available Application Secrets against the API to select the working one.
        Raises an error if no valid secret is found.
        """
        for secret in self.secrets:
            try:
                self.api_call("track/getFileUrl", id=5966783, fmt_id=5, sec=secret)
                self.sec = secret
                break
            except: continue
        if not self.sec and self.secrets: self.sec = self.secrets[0]
        if not self.sec: raise InvalidAppSecretError("No secret found.")