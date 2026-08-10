import re
import os
import logging

from mutagen.flac import FLAC, Picture
import mutagen.id3 as id3
from mutagen.id3 import ID3NoHeaderError
from qobuz_dl.settings import QobuzDLSettings
from qobuz_dl.utils import get_album_artist

logger = logging.getLogger(__name__)


# unicode symbols
COPYRIGHT, PHON_COPYRIGHT = "\u2117", "\u00a9"
# if a metadata block exceeds this, mutagen will raise error
# and the file won't be tagged
FLAC_MAX_BLOCKSIZE = 16777215

ID3_LEGEND = {
    "albumartist": id3.TPE2,
    "album": id3.TALB,
    "artist": id3.TPE1,
    "title": id3.TIT2,
    "date": id3.TDAT,
    "mediatype": id3.TMED,
    "genre": id3.TCON,
    "composer": id3.TCOM,
    "itunesadvisory": id3.TXXX,
    "copyright": id3.TCOP,
    "label": id3.TPUB,
    "barcode": id3.TXXX,
    "isrc": id3.TSRC,
    "comment": id3.COMM,
    "year": id3.TYER,
    "performer": id3.TOPE,
    # --- DB SYNC FEATURE: CUSTOM QOBUZ IDS ---
    "QOBUZ TRACK ID": id3.TXXX,
    "QOBUZ ALBUM ID": id3.TXXX,
    "QOBUZ ALBUM URL": id3.TXXX,
    # --- REPLAYGAIN ---
    "replaygain_track_gain": id3.TXXX,
    "replaygain_track_peak": id3.TXXX,
    # --- CLASSICAL MUSIC ---
    "conductor": id3.TPE3,
    "ensemble": id3.TXXX,
    "work": id3.TIT1,
}

EMB_COVER_NAME = "embed_cover.jpg"

LOCAL_GENRE_MAP = {
    # Elettronica & Dance
    "Électronique": "Electronic",
    "Ambiance": "Ambient",
    
    # Classica & Strumentale
    "Classique": "Classical",
    "Musique de chambre": "Chamber Music",
    "Opéra": "Opera",
    "Chorale": "Choral",
    "Symphonique": "Symphonic",
    
    # Colonne Sonore & Media
    "Bande Originale": "Soundtrack",
    "Musique de film": "Soundtrack",
    "Comédie Musicale": "Musical",
    "Bande originale de jeu vidéo": "Video Game Soundtrack",
    
    # Jazz & Blues
    "Jazz Vocal": "Vocal Jazz",
    "Jazz Contemporain": "Contemporary Jazz",
    
    # World Music & Regionali
    "Musiques du monde": "World",
    "Musique celtique": "Celtic",
    "Musique latine": "Latin",
    "Variété Française": "French Pop",
    "Alternatif et Indé": "Alternative & Indie",
        
    # Varie
    "Enfants": "Children's Music",
    "Berceuses": "Lullabies",
    "Poésie et Littérature": "Spoken Word",
    "Livres Audio": "Audiobooks",
    "Humour": "Comedy",
    "Religieux": "Religious",
    "Détente": "Relaxation",
    "Fêtes": "Holiday",
}

def _get_title_with_version(title: str = "", version: str = "") -> str:
    """
    Constructs a track or album title by appending its version if it exists.

    Args:
        title (str, optional): The original title. Defaults to "".
        version (str, optional): The version of the track/album (e.g., 'Remastered'). Defaults to "".

    Returns:
        str: The combined title and version string.
    """
    item_title = title
    if version:
        item_title = (
            f"{title} ({version})"
            if version.lower() not in title.lower()
            else title
        )
    return item_title


def _get_title(track_dict):
    """
    Constructs a comprehensive title for a track, including version and classical work prefixes.

    Args:
        track_dict (dict): The dictionary containing track metadata.

    Returns:
        str: The fully formatted title string.
    """
    title = track_dict["title"]
    version = track_dict.get("version")
    if version:
        title = f"{title} ({version})"
    # for classical works
    if track_dict.get("work"):
        title = f"{track_dict['work']}: {title}"

    return title


def _format_copyright(s: str) -> str:
    """
    Replaces standard text copyright symbols with their Unicode equivalents.

    Args:
        s (str): The original copyright string containing '(P)' or '(C)'.

    Returns:
        str: The formatted copyright string with Unicode symbols.
    """
    if s:
        s = s.replace("(P)", PHON_COPYRIGHT)
        s = s.replace("(C)", COPYRIGHT)
    return s


def _format_genres(genres: list) -> str:
    """
    Cleans and formats a list of genres, removing duplicates and extracting primary names.

    Args:
        genres (list): A list of genre strings from the Qobuz API.

    Returns:
        str: A comma-separated string of unique, formatted genres.
    """
    genres = re.findall(r"([^\u2192\/]+)", "/".join(genres))
    no_repeats = []
    [no_repeats.append(g) for g in genres if g not in no_repeats]
    return ", ".join(no_repeats)


def _embed_flac_img(root_dir, audio: FLAC):
    """
    Embeds a cover image into a FLAC audio file.

    Ensures the image does not exceed the maximum allowed block size for FLAC metadata 
    to prevent encoding errors.

    Args:
        root_dir (str): The directory containing the audio file and cover image.
        audio (FLAC): The Mutagen FLAC audio object to be tagged.
    """
    emb_image = os.path.join(root_dir, EMB_COVER_NAME)
    multi_emb_image = os.path.join(
        os.path.abspath(os.path.join(root_dir, os.pardir)), EMB_COVER_NAME
    )
    if os.path.isfile(emb_image):
        cover_image = emb_image
    else:
        cover_image = multi_emb_image

    if not os.path.isfile(cover_image):
        logger.debug(f"Cover image not found to embed: {cover_image}")
        return

    try:
        if os.path.getsize(cover_image) > FLAC_MAX_BLOCKSIZE:
            raise Exception(
                "downloaded cover size too large to embed. "
                "turn off `og_cover` to avoid error"
            )

        image = Picture()
        image.type = 3
        image.mime = "image/jpeg"
        image.desc = "cover"
        with open(cover_image, "rb") as img:
            image.data = img.read()
        audio.add_picture(image)
    except Exception as e:
        logger.error(f"Error embedding image: {e}", exc_info=True)


def _embed_id3_img(root_dir, audio: id3.ID3):
    """
    Embeds a cover image into an MP3 file using ID3 tags.

    Args:
        root_dir (str): The directory containing the audio file and cover image.
        audio (id3.ID3): The Mutagen ID3 audio object to be tagged.
    """
    emb_image = os.path.join(root_dir, EMB_COVER_NAME)
    multi_emb_image = os.path.join(
        os.path.abspath(os.path.join(root_dir, os.pardir)), EMB_COVER_NAME
    )
    if os.path.isfile(emb_image):
        cover_image = emb_image
    else:
        cover_image = multi_emb_image

    if not os.path.isfile(cover_image):
        logger.debug(f"Cover image not found to embed: {cover_image}")
        return

    with open(cover_image, "rb") as cover:
        audio.add(id3.APIC(3, "image/jpeg", 3, "", cover.read()))


def tag_flac(
    filename, root_dir, final_name, d: dict, album, istrack=True, em_image=False, settings: QobuzDLSettings = None
):
    """
    Applies metadata tags and cover art to a FLAC audio file.

    Supports advanced tagging features including multi-value tags, ReplayGain injections, 
    and custom Qobuz IDs for local database synchronization. Renames the file to its 
    final destination upon completion.

    Args:
        filename (str): The current path to the audio file.
        root_dir (str): The directory where the file and cover image are located.
        final_name (str): The final designated filename after tagging is complete.
        d (dict): The track or album dictionary containing metadata.
        album (dict): The dictionary containing album-level metadata.
        istrack (bool, optional): Indicates if the file is a single track. Defaults to True.
        em_image (bool, optional): Flag to enable embedding the cover image. Defaults to False.
        settings (QobuzDLSettings, optional): Configuration object for user preferences. Defaults to None.
    """
    audio = FLAC(filename)

    if istrack:
        qobuz_item = d
        qobuz_album = d.get("album", {})
    else:
        qobuz_item = d
        qobuz_album = album

    tags = _get_tags_to_add(qobuz_album, qobuz_item, settings=settings)

    if not settings.no_track_number_tag:
        tags["TRACKNUMBER"] = str(qobuz_item.get("track_number", "1"))
    if not settings.no_track_total_tag:
        tags["TRACKTOTAL"] = str(qobuz_album.get("tracks_count", "1"))
    if not settings.no_disc_number_tag:
        tags["DISCNUMBER"] = str(qobuz_item.get("media_number", "1"))
    if not settings.no_disc_total_tag:
        tags["DISCTOTAL"] = str(qobuz_album.get("media_count", "1"))

    for k, v in tags.items():
        if v:
            # --- MULTI-TAG FEATURE ---
            if getattr(settings, 'multi_value_tags', False) and k == "GENRE" and isinstance(v, str):
                if ", " in v:
                    v = v.split(", ")
            
            audio[k] = v

    if em_image:
        _embed_flac_img(root_dir, audio)

    for junk_tag in ["ENCODER", "ENCODED-BY", "ENCODED_BY"]:
        if junk_tag in audio:
            del audio[junk_tag]
            
    if hasattr(audio, 'tags') and audio.tags is not None:
        audio.tags.vendor = ""

    audio.save(padding=lambda info: 8192)
    
    os.rename(filename, final_name)


def tag_mp3(filename, root_dir, final_name, d, album, istrack=True, em_image=False, settings: QobuzDLSettings = None):
    """
    Applies ID3 metadata tags and cover art to an MP3 audio file.

    Maps custom Qobuz metadata to corresponding ID3 legends and handles standard track 
    and disc numbering. Renames the file upon completion.

    Args:
        filename (str): The current path to the audio file.
        root_dir (str): The directory where the file and cover image are located.
        final_name (str): The final designated filename after tagging is complete.
        d (dict): The track or album dictionary containing metadata.
        album (dict): The dictionary containing album-level metadata.
        istrack (bool, optional): Indicates if the file is a single track. Defaults to True.
        em_image (bool, optional): Flag to enable embedding the cover image. Defaults to False.
        settings (QobuzDLSettings, optional): Configuration object for user preferences. Defaults to None.
    """
    try:
        audio = id3.ID3(filename)
    except ID3NoHeaderError:
        audio = id3.ID3()

    if istrack:
        qobuz_item = d
        qobuz_album = d.get("album", {})
    else:
        qobuz_item = d
        qobuz_album = album

    tags = _get_tags_to_add(qobuz_album, qobuz_item, settings=settings)

    for k, v in tags.items():
        if v:
            id3tag = ID3_LEGEND.get(k.lower()) or ID3_LEGEND.get(k)
            if id3tag:
                if id3tag == id3.TXXX:
                    audio.add(id3tag(encoding=3, desc=k, text=v))
                else:
                    audio[id3tag.__name__] = id3tag(encoding=3, text=v)

    audio["TRCK"] = id3.TRCK(encoding=3,
                             text=f'{str(qobuz_item.get("track_number", "1"))}/{str(qobuz_album.get("tracks_count", "1"))}')
    audio["TPOS"] = id3.TPOS(encoding=3,
                             text=f'{str(qobuz_item.get("media_number", "1"))}/{str(qobuz_album.get("media_count", "1"))}')

    if em_image:
        _embed_id3_img(root_dir, audio)

    audio.pop("TENC", None)
    audio.pop("TSSE", None)

    audio.save(filename, v2_version=3)
    os.rename(filename, final_name)


def _get_tags_to_add(qobuz_album: dict, qobuz_item : dict, settings: QobuzDLSettings = None):
    """
    Extracts and maps metadata from Qobuz API responses into a standardized tag dictionary.

    This core engine processes native Qobuz data including Classical music roles, 
    ReplayGain track/peak values, multi-artist matrices, and custom Qobuz IDs, 
    adhering strictly to the provided configuration flags.

    Args:
        qobuz_album (dict): The dictionary containing album-level metadata.
        qobuz_item (dict): The dictionary containing track-level metadata.
        settings (QobuzDLSettings, optional): Configuration object containing user preferences 
            (e.g., flags to disable specific tags). Defaults to None.

    Returns:
        dict: A dictionary mapping standardized tag keys to their corresponding extracted values.
    """
    tags = dict()
    if not qobuz_album or not qobuz_item:
        return tags

    # Basic Information
    if not settings.no_album_title_tag:
        tags["ALBUM"] = _get_title_with_version(title=qobuz_album.get("title", ""),
                                                version=qobuz_album.get("version", ""))
    if not settings.no_track_title_tag:
        tags["TITLE"] = _get_title_with_version(title=qobuz_item.get("title", ""),
                                                version=qobuz_item.get("version", ""))

    # Artist Information
    if not settings.no_album_artist_tag:
        tags["ALBUMARTIST"] = get_album_artist(qobuz_album)
        
    if not settings.no_track_artist_tag:
        main_artist = qobuz_item.get("performer", {}).get("name", "") or qobuz_album.get("artist", {}).get("name", "")
        artists = [main_artist] if main_artist else []
        
        performers_str = qobuz_item.get("performers", "")
        if performers_str:
            for performer_block in performers_str.split(" - "):
                parts = [p.strip() for p in performer_block.split(", ")]
                if len(parts) > 1:
                    name = parts[0]
                    roles = parts[1:]
                    
                    if "FeaturedArtist" in roles or "MainArtist" in roles:
                        if name not in artists:
                            artists.append(name)
        
        if len(artists) == 1:
            tags["ARTIST"] = artists[0]
        elif len(artists) > 1:
            tags["ARTIST"] = artists
        else:
            tags["ARTIST"] = ""

    if not settings.no_composer_tag:
        composers = []
        performers_str = qobuz_item.get("performers", "")
        
        if performers_str:
            for performer_block in performers_str.split(" - "):
                parts = [p.strip() for p in performer_block.split(", ")]
                if len(parts) > 1:
                    name = parts[0]
                    roles = parts[1:]
                    
                    if "Composer" in roles or "ComposerLyricist" in roles:
                        if name not in composers:
                            composers.append(name)
                            
        if not composers:
            main_composer = qobuz_item.get("composer", {}).get("name", "")
            if main_composer:
                composers.append(main_composer)

        if len(composers) == 1:
            tags["COMPOSER"] = composers[0]
        elif len(composers) > 1:
            tags["COMPOSER"] = composers
        else:
            tags["COMPOSER"] = ""

    # Release Information
    release_date = qobuz_album.get("release_date_original", "")
    if not settings.no_release_date_tag:
        tags["DATE"] = release_date        
    if not settings.no_genre_tag:
        raw_main_genre = qobuz_album.get("genre", {}).get("name")
        main_genre = LOCAL_GENRE_MAP.get(raw_main_genre, raw_main_genre) if raw_main_genre else None
        
        raw_genres = qobuz_album.get("genres_list", [])
        if main_genre:
            if raw_genres:
                raw_genres[0] = main_genre
            else:
                raw_genres = [main_genre]
                
        extracted_genres = re.findall(r"([^\u2192]+)", " \u2192 ".join(raw_genres))
        
        final_genres = []
        for g in extracted_genres:
            clean_g = g.strip()
            translated = LOCAL_GENRE_MAP.get(clean_g, clean_g)
            if translated not in final_genres:
                final_genres.append(translated)
                
        tags["GENRE"] = ", ".join(final_genres)
    if not settings.no_label_tag:
        tags["COPYRIGHT"] = _format_copyright(qobuz_album.get("copyright", "n/a"))
    if not settings.no_label_tag:
        tags["LABEL"] = re.sub(r'\s+',' ', qobuz_album.get("label", {}).get("name", ""))
    if not settings.no_isrc_tag:
        tags["ISRC"] = qobuz_item.get("isrc", "")
    if not settings.no_upc_tag:
        tags["BARCODE"] = qobuz_album.get("upc", "")

    # Media Information
    if not settings.no_media_type_tag:
        tags["MEDIATYPE"] = qobuz_album.get("product_type", "").upper()
    if not settings.no_explicit_tag:
        tags["ITUNESADVISORY"] = "1" if qobuz_item.get("parental_warning", False) else ""

    # --- REPLAYGAIN TAGS ---
    if not getattr(settings, 'no_replaygain_tag', False):
        audio_info = qobuz_item.get("audio_info", {})
        if audio_info:
            rg_gain = audio_info.get("replaygain_track_gain")
            rg_peak = audio_info.get("replaygain_track_peak")
            
            if rg_gain is not None:
                tags["REPLAYGAIN_TRACK_GAIN"] = f"{rg_gain} dB"
            if rg_peak is not None:
                tags["REPLAYGAIN_TRACK_PEAK"] = str(rg_peak)

    # --- CLASSICAL MUSIC TAGS ---
    work = qobuz_item.get("work")
    if work and not getattr(settings, 'no_work_tag', False):
        tags["WORK"] = work

    conductors = []
    ensembles = []
    performers_str = qobuz_item.get("performers", "")
    
    if performers_str:
        for performer_block in performers_str.split(" - "):
            parts = [p.strip() for p in performer_block.split(", ")]
            if len(parts) > 1:
                name = parts[0]
                roles = parts[1:]
                
                if "Conductor" in roles:
                    conductors.append(name)
                if any(role in roles for role in ["Orchestra", "Ensemble", "Choir"]):
                    ensembles.append(name)

    if conductors and not getattr(settings, 'no_conductor_tag', False):
        tags["CONDUCTOR"] = conductors if len(conductors) > 1 else conductors[0]
    if ensembles and not getattr(settings, 'no_ensemble_tag', False):
        tags["ENSEMBLE"] = ensembles if len(ensembles) > 1 else ensembles[0]
    # ----------------------------

    # --- DB SYNC FEATURE: SAVE QOBUZ IDS ---
    track_id = qobuz_item.get("id")
    if track_id:
        tags["QOBUZTRACKID"] = str(track_id)
        
    album_id = qobuz_album.get("id")
    if album_id:
        tags["QOBUZALBUMID"] = str(album_id)

    # --- DIRECT ALBUM URL TAGGING ---
    if not getattr(settings, 'no_album_url_tag', False):
        if album_id:
            raw_title = str(qobuz_album.get("title", "album"))
            slug = re.sub(r'[^a-z0-9]+', '-', raw_title.lower()).strip('-')
            tags["QOBUZ ALBUM URL"] = f"https://www.qobuz.com/album/{slug}/{album_id}"

    return tags