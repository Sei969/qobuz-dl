import re
import string
import os
import logging
import subprocess
import time
import unicodedata

from mutagen.mp3 import EasyMP3
from mutagen.flac import FLAC

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

EXTENSIONS = (".mp3", ".flac")


class PartialFormatter(string.Formatter):
    def __init__(self, missing="n/a", bad_fmt="n/a"):
        self.missing, self.bad_fmt = missing, bad_fmt

    def get_field(self, field_name, args, kwargs):
        try:
            val = super(PartialFormatter, self).get_field(field_name, args, kwargs)
        except (KeyError, AttributeError):
            val = None, field_name
        return val

    def format_field(self, value, spec):
        if not value:
            return self.missing
        try:
            return super(PartialFormatter, self).format_field(value, spec)
        except ValueError:
            if self.bad_fmt:
                return self.bad_fmt
            raise

def make_m3u(pl_directory, remote_items=None):
    """
    Generates a .m3u playlist file.
    If remote_items (Qobuz API playlist order) is provided, it matches the files
    by QOBUZTRACKID to preserve the exact online order, ignoring filenames.
    """
    track_list = ["#EXTM3U"]
    rel_folder = os.path.basename(os.path.normpath(pl_directory))
    pl_name = rel_folder + ".m3u"
    pl_full_path = os.path.join(pl_directory, pl_name)

    # 1. Scansiona la cartella locale e mappa i file tramite il loro QOBUZTRACKID
    local_tracks = {}
    for local, dirs, files in os.walk(pl_directory):
        dirs.sort()
        for f in files:
            if os.path.splitext(f)[-1].lower() in EXTENSIONS:
                audio_full_path = os.path.abspath(os.path.join(local, f))
                try:
                    pl_item = (
                        EasyMP3(audio_full_path)
                        if audio_full_path.lower().endswith(".mp3")
                        else FLAC(audio_full_path)
                    )
                    
                    track_id = None
                    if audio_full_path.lower().endswith('.flac'):
                        track_id = pl_item.get("QOBUZTRACKID", [None])[0]
                    else:
                        txxx = pl_item.get("TXXX:QOBUZTRACKID")
                        if txxx:
                            track_id = txxx.text[0]
                    
                    if track_id:
                        local_tracks[str(track_id)] = audio_full_path
                    else:
                        local_tracks[audio_full_path] = audio_full_path
                except Exception as e:
                    logger.error(f"Error reading tags for {f}: {e}")

    ordered_files = []

    # 2. Se abbiamo l'ordine ufficiale della playlist da Qobuz, usiamo quello
    if remote_items:
        for item in remote_items:
            tid = str(item.get("id"))
            if tid in local_tracks:
                ordered_files.append(local_tracks[tid])
    # 3. Fallback (es. per interi album o assenza di remote_items): ordine naturale
    else:
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
        ordered_files = sorted(local_tracks.values(), key=natural_sort_key)

    # 4. Genera il file .m3u
    for audio_full_path in ordered_files:
        audio_rel_path = os.path.relpath(audio_full_path, pl_directory)
        try:
            pl_item = (
                EasyMP3(audio_full_path)
                if audio_full_path.lower().endswith(".mp3")
                else FLAC(audio_full_path)
            )

            title = pl_item.get("TITLE", ["Unknown Title"])[0]
            artist = pl_item.get("ARTIST", ["Unknown Artist"])[0]
            length = int(pl_item.info.length) if hasattr(pl_item.info, 'length') else 0

            index = f"#EXTINF:{length}, {artist} - {title}\n{audio_rel_path}"
            track_list.append(index)
        except Exception as e:
            logger.error(f"Error processing {audio_full_path}: {e}")
            continue

    if len(track_list) > 1:
        with open(pl_full_path, "w", encoding="utf-8") as pl:
            pl.write("\n".join(track_list))


def smart_discography_filter(
    contents: list, save_space: bool = False, skip_extras: bool = False
) -> list:
    """When downloading some artists' discography, many random and spam-like
    albums can get downloaded. This helps filter those out to just get the good stuff.

    This function removes:
        * albums by other artists, which may contain a feature from the requested artist
        * duplicate albums in different qualities
        * (optionally) removes collector's, deluxe, live albums

    :param list contents: contents returned by qobuz API
    :param bool save_space: choose highest bit depth, lowest sampling rate
    :param bool remove_extras: remove albums with extra material (i.e. live, deluxe,...)
    :returns: filtered items list
    """

    # for debugging
    def print_album(album: dict) -> None:
        logger.debug(
            f"{album['title']} - {album.get('version', '~~')} "
            "({album['maximum_bit_depth']}/{album['maximum_sampling_rate']}"
            " by {album['artist']['name']}) {album['id']}"
        )

    TYPE_REGEXES = {
        "remaster": r"(?i)(re)?master(ed)?",
        "extra": r"(?i)(anniversary|deluxe|live|collector|demo|expanded)",
    }

    def is_type(album_t: str, album: dict) -> bool:
        """Check if album is of type `album_t`"""
        version = album.get("version", "")
        title = album.get("title", "")
        regex = TYPE_REGEXES[album_t]
        return re.search(regex, f"{title} {version}") is not None

    def essence(album: dict) -> str:
        """Ignore text in parens/brackets, return all lowercase.
        Used to group two albums that may be named similarly, but not exactly
        the same.
        """
        r = re.match(r"([^\(]+)(?:\s*[\(\[][^\)][\)\]])*", album)
        return r.group(1).strip().lower()

    requested_artist = contents[0]["name"]
    items = [item["albums"]["items"] for item in contents][0]

    # use dicts to group duplicate albums together by title
    title_grouped = dict()
    for item in items:
        title_ = essence(item["title"])
        if title_ not in title_grouped:  # ?
            #            if (t := essence(item["title"])) not in title_grouped:
            title_grouped[title_] = []
        title_grouped[title_].append(item)

    items = []
    for albums in title_grouped.values():
        best_bit_depth = max(a["maximum_bit_depth"] for a in albums)
        get_best = min if save_space else max
        best_sampling_rate = get_best(
            a["maximum_sampling_rate"]
            for a in albums
            if a["maximum_bit_depth"] == best_bit_depth
        )
        remaster_exists = any(is_type("remaster", a) for a in albums)

        def is_valid(album: dict) -> bool:
            return (
                album["maximum_bit_depth"] == best_bit_depth
                and album["maximum_sampling_rate"] == best_sampling_rate
                and album["artist"]["name"] == requested_artist
                and not (  # states that are not allowed
                    (remaster_exists and not is_type("remaster", album))
                    or (skip_extras and is_type("extra", album))
                )
            )

        filtered = tuple(filter(is_valid, albums))
        # most of the time, len is 0 or 1.
        # if greater, it is a complete duplicate,
        # so it doesn't matter which is chosen
        if len(filtered) >= 1:
            items.append(filtered[0])

    return items


def format_duration(duration):
    return time.strftime("%H:%M:%S", time.gmtime(duration))


def create_and_return_dir(directory):
    fix = os.path.abspath(os.path.expanduser(directory))
    os.makedirs(fix, exist_ok=True)
    return fix


def get_url_info(url):
    """Returns the type of the url and the id.

    Compatible with urls of the form:
        https://www.qobuz.com/us-en/{type}/{name}/{id}
        https://open.qobuz.com/{type}/{id}
        https://play.qobuz.com/{type}/{id}
        /us-en/{type}/-/{id}
    """

    r = re.search(
        r"(?:https:\/\/(?:w{3}|open|play)\.qobuz\.com)?(?:\/[a-z]{2}-[a-z]{2})"
        r"?\/(album|artist|track|playlist|label)(?:\/[-\w\d]+)?\/([\w\d]+)",
        url,
    )
    return r.groups()


def get_album_artist(qobuz_album: dict) -> list:
    """
    Get the album's main artists from the Qobuz API response.
    Returns a LIST of strings to ensure true Multi-Artist Tagging 
    (discrete Vorbis Comments for FLAC files).
    :param qobuz_album: Qobuz API response.
    :return: A list of the album's main artists.
    """
    try:
        # Se la chiave 'artists' non esiste, ritorna il singolo artista in una lista
        if not qobuz_album.get("artists"):
            single_artist = qobuz_album.get("artist", {}).get("name", "")
            return [single_artist] if single_artist else []

        # Filtra l'array isolando solo chi ha il ruolo 'main-artist'
        main_artists = list(filter(lambda a: "main-artist" in a.get("roles", []),
                                   qobuz_album.get("artists", [])))
        
        # Estrae i nomi puri e li restituisce come lista separata
        if main_artists:
            return [a["name"] for a in main_artists]
        else:
            single_artist = qobuz_album.get("artist", {}).get("name", "")
            return [single_artist] if single_artist else []
            
    except Exception as e:
        logger.error(f"Error getting album artist: {str(e)}")
        single_artist = qobuz_album.get("artist", {}).get("name", "")
        return [single_artist] if single_artist else []


def clean_filename(filename: str) -> str:
    """
    Clean up redundant special characters, spaces, separators in filenames
    and normalize Unicode characters to NFC form
    :param filename:
    :return:
    """
    # First normalize the Unicode string to NFC form
    filename = unicodedata.normalize('NFC', filename)
    
    # Clean up redundant spaces, separators, and brackets

    # Merge multiple separators (supports spaces, commas, periods, Chinese commas, colons, semicolons, vertical bars, slashes, backslashes, underscores. Does not support the - symbol) into one
    filename = re.sub(r'(?:\s*([,\.\:\;\|/\\_])\s*){2,}', r'\1 ', filename)

    # Define all paired bracket patterns
    patterns = [
        # Handle paired brackets containing only special characters
        (r'\(\s*\W*\s*\)', ''),  # (...)
        (r'\[\s*\W*\s*\]', ''),  # [...]
        (r'\{\s*\W*\s*\}', ''),  # {...}
        (r'<\s*\W*\s*>', ''),  # <...>
        (r'《\s*\W*\s*》', ''),  # 《...》
        (r'〈\s*\W*\s*〉', ''),  # 〈...〉
        (r'「\s*\W*\s*」', ''),  # 「...」
        (r'『\s*\W*\s*』', ''),  # 『...』
        (r'（\s*\W*\s*）', ''),  # （...）
        (r'［\s*\W*\s*］', ''),  # ［...］
        (r'【\s*\W*\s*】', ''),  # 【...】

        # Handle edge cases - remove all special characters and spaces at boundaries
        # If a left bracket is followed by a separator, or a separator is followed by a right bracket, remove them
        (r'(?<=[\(\[\{<《〈「『（［【])(\s*[,\.\:\;\|/\\_]\s*)\b', ''),
        (r'\b(\s*[,\.\:\;\|/\\_]\s*)(?=[】］）』」〉》>\}\]\)])', ''),
    ]

    # Apply each pattern sequentially
    for pattern, replacement in patterns:
        filename = re.sub(pattern, replacement, filename)

    # Merge multiple spaces
    filename = re.sub(r'\s+', ' ', filename)
    return invalid_chars_to_fullwidth(filename.strip().strip(".").strip())


def invalid_chars_to_fullwidth(filename):
    """
    Convert illegal characters in filenames to full-width characters
    :param filename:
    :return:
    """
    # Illegal characters to full-width characters
    invalid_to_fullwidth = {
        '/': '／',
        '\\': '＼',
        ':': '：',
        '*': '＊',
        '?': '？',
        '"': '＂',
        '<': '＜',
        '>': '＞',
        '|': '｜',
    }

    for invalid_char, fullwidth_char in invalid_to_fullwidth.items():
        filename = filename.replace(invalid_char, fullwidth_char)
    return filename