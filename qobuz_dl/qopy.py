import base64
import hashlib
import logging
import time

import requests
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from qobuz_dl.exceptions import (
    AuthenticationError,
    IneligibleError,
    InvalidAppIdError,
    InvalidAppSecretError,
    InvalidQuality,
)
from qobuz_dl.color import GREEN, YELLOW, OFF, RESET

try:
    from qobuz_dl.bundle import Bundle
except ImportError:
    Bundle = None

logger = logging.getLogger(__name__)

class Client:
    def __init__(self, email, pwd, app_id, secrets, force_english=True):
        logger.info(f"{YELLOW}Logging...{OFF}")
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
                "Accept-Language": "en-US,en;q=0.9",
                "X-Locale": "en_US"
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
        self.auth(email, pwd)
        self.cfg_setup()

    def _login_with_password(self, email, password):
        data = {"email": email, "password": password, "app_id": self.id}
        r = self.session.post(self.base + "user/login", data=data)
        if r.status_code == 401: raise AuthenticationError("Invalid credentials.\n" + RESET)
        r.raise_for_status()
        return r.json()

    def auth(self, email, pwd):
        if len(pwd) > 60:
            self.uat = pwd
        else:
            usr_info = self._login_with_password(email, pwd)
            self.uat = usr_info["user_auth_token"]
        
        self.session.headers.update({"X-User-Auth-Token": self.uat})
        
        try:
            user_info = self.api_call("user/get")
            cred = user_info.get("credential") or user_info.get("user", {}).get("credential", {})
            self.label = cred.get("parameters", {}).get("short_label", "Studio")
            logger.info(f"{GREEN}Logged: OK (Membership: {self.label}){OFF}")
        except Exception:
            logger.info(f"{YELLOW}[!] Profile validation bypassed.{OFF}")
            self.label = "Studio"

    # NEW CRYPTOGRAPHIC FUNCTIONS (Patch 0004)
    def _modern_sig(self, epoint, params, sec):
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
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    def _derive_session_key(self):
        salt, info = self.session_infos.split(".")
        return HKDF(
            algorithm=hashes.SHA256(),
            length=16,
            salt=self._b64url_decode(salt),
            info=self._b64url_decode(info),
        ).derive(bytes.fromhex(self.sec))

    def _unwrap_track_key(self, key_token):
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
        if epoint == "track/getFileUrl":
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

        if epoint == "user/login":
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
            if "invalid" in r.text:
                raise AuthenticationError("Invalid email or password.")
            else:
                logger.info(f"{GREEN}Logged: OK")
        elif (
            epoint in ["track/getFileUrl", "favorite/getUserFavorites", "file/url"]
            and r.status_code == 400
        ):
            raise InvalidAppSecretError(f"Invalid app secret: {r.json()}.\n" + RESET)
        
        if epoint == "user/get" and r.status_code == 400: return {}
        r.raise_for_status()
        return r.json()

    def multi_meta(self, epoint, key, id, type):
        total, offset = 1, 0
        while total > 0:
            j = self.api_call(epoint, id=id, offset=offset, type=type)
            res = j[type] if type and type in j else j
            yield res
            if offset == 0: total = res.get(key, 0) - 500
            else: total -= 500
            offset += 500

    # --- METADATA FUNCTIONS (Do not delete!) ---
    def get_album_meta(self, id): 
        return self.api_call("album/get", id=id)
        
    def get_track_meta(self, id): 
        return self.api_call("track/get", id=id)

    # --- SEARCH FUNCTIONS (Crash-Proof) ---
    def search_albums(self, query, limit=20):
        try: return self.api_call("catalog/search", query=query, type="albums", limit=limit)
        except Exception: return {}

    def search_tracks(self, query, limit=20):
        try: return self.api_call("catalog/search", query=query, type="tracks", limit=limit)
        except Exception: return {}

    def search_playlists(self, query, limit=20):
        try: return self.api_call("catalog/search", query=query, type="playlists", limit=limit)
        except Exception: return {}

    def search_artists(self, query, limit=20):
        try: return self.api_call("catalog/search", query=query, type="artists", limit=limit)
        except Exception: return {}
        
    # NEW GET_TRACK_URL (Patch 0004)
    def get_track_url(self, id, fmt_id, force_segments=False):
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

    def get_artist_meta(self, id): return self.multi_meta("artist/get", "albums_count", id, None)
    def get_plist_meta(self, id): return self.multi_meta("playlist/get", "tracks_count", id, None)
    def get_label_meta(self, id): return self.multi_meta("label/get", "albums_count", id, None)
    
    def cfg_setup(self):
        for secret in self.secrets:
            try:
                self.api_call("track/getFileUrl", id=5966783, fmt_id=5, sec=secret)
                self.sec = secret
                break
            except: continue
        if not self.sec and self.secrets: self.sec = self.secrets[0]
        if not self.sec: raise InvalidAppSecretError("No secret found.")