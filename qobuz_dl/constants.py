# Default format strings
DEFAULT_FOLDER = "{album_artist} - {album_title} ({year}) [{format} {bit_depth}]"
DEFAULT_TRACK = "{track_number} - {track_title_base}"
DEFAULT_MULTIPLE_DISC_TRACK = "{disc_number}.{track_number} - {track_title_base}"
# Album artist names that mark a compilation of various artists (config key: various_artists_aliases)
DEFAULT_VARIOUS_ARTISTS_ALIASES = (
    "various artists, various, va, artistes divers, verschiedene interpreten, "
    "varios artistas, artisti vari, vari"
)
# character length for the longest allowed album track filename (folder_name + track_name + extension).
OK_MAX_CHARACTER_LENGTH = 180