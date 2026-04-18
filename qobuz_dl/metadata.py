import re
import os
import logging

from mutagen.flac import FLAC, Picture
import mutagen.id3 as id3
from mutagen.id3 import ID3NoHeaderError
from qobuz_dl.settings import QobuzDLSettings
# Rimosso flac_fix_md5s da qui
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
    "QOBUZTRACKID": id3.TXXX,
    "QOBUZALBUMID": id3.TXXX,
    # --- REPLAYGAIN ---
    "replaygain_track_gain": id3.TXXX,
    "replaygain_track_peak": id3.TXXX,
}

EMB_COVER_NAME = "embed_cover.jpg"


def _get_title_with_version(title: str = "", version: str = "") -> str:
    """
    Get the title and append the version to the title, if available
    :param title:
    :param version:
    :return:
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
    title = track_dict["title"]
    version = track_dict.get("version")
    if version:
        title = f"{title} ({version})"
    # for classical works
    if track_dict.get("work"):
        title = f"{track_dict['work']}: {title}"

    return title


def _format_copyright(s: str) -> str:
    if s:
        s = s.replace("(P)", PHON_COPYRIGHT)
        s = s.replace("(C)", COPYRIGHT)
    return s


def _format_genres(genres: list) -> str:
    """Fixes the weirdly formatted genre lists returned by the API.
    >>> g = ['Pop/Rock', 'Pop/Rock→Rock', 'Pop/Rock→Rock→Alternatif et Indé']
    >>> _format_genres(g)
    'Pop, Rock, Alternatif et Indé'
    """
    genres = re.findall(r"([^\u2192\/]+)", "/".join(genres))
    no_repeats = []
    [no_repeats.append(g) for g in genres if g not in no_repeats]
    return ", ".join(no_repeats)


def _embed_flac_img(root_dir, audio: FLAC):
    emb_image = os.path.join(root_dir, EMB_COVER_NAME)
    multi_emb_image = os.path.join(
        os.path.abspath(os.path.join(root_dir, os.pardir)), EMB_COVER_NAME
    )
    if os.path.isfile(emb_image):
        cover_image = emb_image
    else:
        cover_image = multi_emb_image

    try:
        # rest of the metadata still gets embedded
        # when the image size is too big
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
    emb_image = os.path.join(root_dir, EMB_COVER_NAME)
    multi_emb_image = os.path.join(
        os.path.abspath(os.path.join(root_dir, os.pardir)), EMB_COVER_NAME
    )
    if os.path.isfile(emb_image):
        cover_image = emb_image
    else:
        cover_image = multi_emb_image

    with open(cover_image, "rb") as cover:
        audio.add(id3.APIC(3, "image/jpeg", 3, "", cover.read()))


# Use KeyError catching instead of dict.get to avoid empty tags
def tag_flac(
    filename, root_dir, final_name, d: dict, album, istrack=True, em_image=False, settings: QobuzDLSettings = None
):
    """
    Tag a FLAC file
    """
    audio = FLAC(filename)

    if istrack:
        qobuz_item = d
        qobuz_album = d.get("album", {})
    else:
        qobuz_item = d
        qobuz_album = album

    # temporarily holds metadata
    tags = _get_tags_to_add(qobuz_album, qobuz_item, settings=settings)

    # Track Information
    if not settings.no_track_number_tag:
        tags["TRACKNUMBER"] = str(qobuz_item.get("track_number", "1"))
    if not settings.no_track_total_tag:
        tags["TRACKTOTAL"] = str(qobuz_album.get("tracks_count", "1"))
    if not settings.no_disc_number_tag:
        tags["DISCNUMBER"] = str(qobuz_item.get("media_number", "1"))
    if not settings.no_disc_total_tag:
        tags["DISCTOTAL"] = str(qobuz_album.get("media_count", "1"))

    # write metadata in `tags` to file
    for k, v in tags.items():
        if v:
            audio[k] = v

    if em_image:
        _embed_flac_img(root_dir, audio)

    audio.save()
    os.rename(filename, final_name)


def tag_mp3(filename, root_dir, final_name, d, album, istrack=True, em_image=False, settings: QobuzDLSettings = None):
    """
    Tag an mp3 file
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

    # temporarily holds metadata
    tags = _get_tags_to_add(qobuz_album, qobuz_item, settings=settings)

    # write metadata in `tags` to file
    for k, v in tags.items():
        if v:
            # Fix compatibilità ID3_LEGEND minuscolo vs tags maiuscolo
            id3tag = ID3_LEGEND.get(k.lower()) or ID3_LEGEND.get(k)
            if id3tag:
                if id3tag == id3.TXXX:
                    audio.add(id3tag(encoding=3, desc=k, text=v))
                else:
                    audio[id3tag.__name__] = id3tag(encoding=3, text=v)

    # track information
    audio["TRCK"] = id3.TRCK(encoding=3,
                             text=f'{str(qobuz_item.get("track_number", "1"))}/{str(qobuz_album.get("tracks_count", "1"))}')
    audio["TPOS"] = id3.TPOS(encoding=3,
                             text=f'{str(qobuz_item.get("media_number", "1"))}/{str(qobuz_album.get("media_count", "1"))}')

    if em_image:
        _embed_id3_img(root_dir, audio)

    audio.save(filename, v2_version=3)
    os.rename(filename, final_name)

def _get_tags_to_add(qobuz_album: dict, qobuz_item : dict, settings: QobuzDLSettings = None):
    """
    get tags data from album and track metadata
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
        # 1. Cattura l'artista principale
        main_artist = qobuz_item.get("performer", {}).get("name", "") or qobuz_album.get("artist", {}).get("name", "")
        artists = [main_artist] if main_artist else []
        
        # 2. Integrazione patch per catturare gli ospiti
        performers_str = qobuz_item.get("performers", "")
        if performers_str:
            for i in performers_str.split(" - "):
                if "FeaturedArtist" in i:
                    artists.append(i.replace(", FeaturedArtist", "").strip())
        
        # 3. Salva nel file musicale
        if len(artists) == 1:
            tags["ARTIST"] = artists[0]
        elif len(artists) > 1:
            tags["ARTIST"] = artists
        else:
            tags["ARTIST"] = ""

    if not settings.no_composer_tag:
        tags["COMPOSER"] = qobuz_item.get("composer", {}).get("name", "")

    # Release Information
    release_date = qobuz_album.get("release_date_original", "")
    if not settings.no_release_date_tag:
        tags["DATE"] = release_date
        tags["YEAR"] = release_date[:4] if release_date else ""
    if not settings.no_genre_tag:
        tags["GENRE"] = _format_genres(qobuz_album.get("genres_list", []))
    if not settings.no_label_tag:
        tags["COPYRIGHT"] = _format_copyright(qobuz_album.get("copyright", "n/a"))
    if not settings.no_label_tag:
        # Qobuz sometimes has multiple spaces in place of where a single space should be when it comes to Labels
        tags["LABEL"] = re.sub(r'\s+',' ', qobuz_album.get("label", {}).get("name", ""))
    if not settings.no_isrc_tag:
        tags["ISRC"] = qobuz_item.get("isrc", "")
    if not settings.no_upc_tag:
        tags["BARCODE"] = qobuz_album.get("upc", "")

    # Media Information
    if not settings.no_media_type_tag:
        tags["MEDIATYPE"] = qobuz_album.get("product_type", "").upper()
    if not settings.no_explicit_tag:
        tags["ITUNESADVISORY"] = "1" if qobuz_album.get("parental_warning", False) else "0"

    # --- NEW: REPLAYGAIN TAGS ---
    audio_info = qobuz_item.get("audio_info", {})
    if audio_info:
        rg_gain = audio_info.get("replaygain_track_gain")
        rg_peak = audio_info.get("replaygain_track_peak")
        
        if rg_gain is not None:
            tags["REPLAYGAIN_TRACK_GAIN"] = f"{rg_gain} dB"
        if rg_peak is not None:
            tags["REPLAYGAIN_TRACK_PEAK"] = str(rg_peak)
    # ----------------------------

    # --- DB SYNC FEATURE: SAVE QOBUZ IDS ---
    # These invisible tags allow the sync tool to rebuild
    # the local database instantly by scanning the files
    track_id = qobuz_item.get("id")
    if track_id:
        tags["QOBUZTRACKID"] = str(track_id)
        
    album_id = qobuz_album.get("id")
    if album_id:
        tags["QOBUZALBUMID"] = str(album_id)

    return tags