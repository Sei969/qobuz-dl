from qobuz_dl.constants import DEFAULT_FOLDER, DEFAULT_TRACK, DEFAULT_MULTIPLE_DISC_TRACK

class QobuzDLSettings:
    def __init__(self, **kwargs):
        # basic options
        self.email = kwargs.get('email')
        self.password = kwargs.get('password')
        self.default_folder = kwargs.get('default_folder', 'QobuzDownloads')
        self.default_quality = kwargs.get('default_quality', 6)
        self.default_limit = kwargs.get('default_limit', 20)
        self.no_m3u = kwargs.get('no_m3u', False)
        self.albums_only = kwargs.get('albums_only', False)
        self.no_fallback = not kwargs.get('no_fallback', False)
        self.no_database = kwargs.get('no_database', False)
        self.app_id = kwargs.get('app_id')
        self.secrets = kwargs.get('secrets')
        self.folder_format = kwargs.get('folder_format')
        self.fallback_folder_format = kwargs.get('fallback_folder_format', DEFAULT_FOLDER)
        self.track_format = kwargs.get('track_format')
        self.smart_discography = kwargs.get('smart_discography', False)
        self.legacy_charmap = kwargs.get('legacy_charmap', False)
        
        # tag options
        self.no_album_artist_tag = kwargs.get('no_album_artist_tag', False)
        self.no_album_title_tag = kwargs.get('no_album_title_tag', False)
        self.no_track_artist_tag = kwargs.get('no_track_artist_tag', False)
        self.no_track_title_tag = kwargs.get('no_track_title_tag', False)
        self.no_release_date_tag = kwargs.get('no_release_date_tag', False)
        self.no_media_type_tag = kwargs.get('no_media_type_tag', False)
        self.no_genre_tag = kwargs.get('no_genre_tag', False)
        self.no_track_number_tag = kwargs.get('no_track_number_tag', False)
        self.no_track_total_tag = kwargs.get('no_track_total_tag', False)
        self.no_disc_number_tag = kwargs.get('no_disc_number_tag', False)
        self.no_disc_total_tag = kwargs.get('no_disc_total_tag', False)
        self.no_composer_tag = kwargs.get('no_composer_tag', False)
        self.no_explicit_tag = kwargs.get('no_explicit_tag', False)
        self.no_copyright_tag = kwargs.get('no_copyright_tag', False)
        self.no_label_tag = kwargs.get('no_label_tag', False)
        self.no_upc_tag = kwargs.get('no_upc_tag', False)
        self.no_isrc_tag = kwargs.get('no_isrc_tag', False)

        # cover options
        self.embed_art = kwargs.get('embed_art', False)
        self.cover_og_quality = kwargs.get('og_cover', False)
        self.no_cover = kwargs.get('no_cover', False)
        self.embedded_art_size = kwargs.get('embedded_art_size', '600')
        self.saved_art_size = kwargs.get('saved_art_size', 'org')

        # multiple disc option
        self.multiple_disc_prefix = kwargs.get('multiple_disc_prefix', 'CD')
        self.multiple_disc_one_dir = kwargs.get('multiple_disc_one_dir', False)
        self.multiple_disc_track_format = kwargs.get(
            'multiple_disc_track_format', 
            DEFAULT_MULTIPLE_DISC_TRACK
        )

        # Add parallel download thread count option
        self.max_workers = int(kwargs.get('max_workers', 3))

        # user_auth_token
        self.user_auth_token = kwargs.get('user_auth_token', '')

    @staticmethod
    def from_arguments_configparser(arguments, config):
        """Creating Configuration Objects from Command Line Parameters and Configuration Files
        
        Args:
            arguments: Parsed command line arguments
            config: ConfigParser object
            
        Returns:
            QobuzDLSettings: Configuration object
        """
        # basic options
        kwargs = {
            'email': config.get("DEFAULT", "email", fallback=""),
            'password': config.get("DEFAULT", "password", fallback=""),
            'default_folder': arguments.directory or config.get("DEFAULT", "default_folder", fallback="QobuzDownloads"),
            'default_quality': arguments.quality or config.get("DEFAULT", "default_quality", fallback="6"),
            'default_limit': config.get("DEFAULT", "default_limit", fallback="20"),
            'no_m3u': arguments.no_m3u or config.getboolean("DEFAULT", "no_m3u", fallback=False),
            'albums_only': arguments.albums_only or config.getboolean("DEFAULT", "albums_only", fallback=False),
            'no_fallback': arguments.no_fallback or config.getboolean("DEFAULT", "no_fallback", fallback=False),
            'no_database': arguments.no_db or config.getboolean("DEFAULT", "no_database", fallback=False),
            'app_id': config.get("DEFAULT", "app_id", fallback=""),
            'secrets': [s for s in config.get("DEFAULT", "secrets", fallback="").split(",") if s],
            'folder_format': arguments.folder_format or config.get("DEFAULT", "folder_format", fallback=DEFAULT_FOLDER),
            'fallback_folder_format': arguments.fallback_folder_format or config.get("DEFAULT", "fallback_folder_format", fallback=DEFAULT_FOLDER),
            'track_format': arguments.track_format or config.get("DEFAULT", "track_format", fallback=DEFAULT_TRACK),
            'smart_discography': arguments.smart_discography or config.getboolean("DEFAULT", "smart_discography", fallback=False),
            
            # cover options
            'embed_art': arguments.embed_art or config.getboolean("DEFAULT", "embed_art", fallback=True),
            'og_cover': arguments.og_cover or config.getboolean("DEFAULT", "og_cover", fallback=False),
            'no_cover': arguments.no_cover or config.getboolean("DEFAULT", "no_cover", fallback=False),
            'embedded_art_size': arguments.embedded_art_size or config.get("DEFAULT", "embedded_art_size", fallback="600"),
            'saved_art_size': arguments.saved_art_size or config.get("DEFAULT", "saved_art_size", fallback="org"),
            
            # multiple disc option
            'multiple_disc_prefix': arguments.multiple_disc_prefix or config.get("DEFAULT", "multiple_disc_prefix", fallback="CD"),
            'multiple_disc_one_dir': arguments.multiple_disc_one_dir or config.getboolean("DEFAULT", "multiple_disc_one_dir", fallback=False),
            'multiple_disc_track_format': arguments.multiple_disc_track_format or config.get("DEFAULT", "multiple_disc_track_format", fallback="{disc_number}.{track_number} - {track_title}"),
                                 
            # tag options
            'no_album_artist_tag': arguments.no_album_artist_tag or config.getboolean("DEFAULT", "no_album_artist_tag", fallback=False),
            'no_album_title_tag': arguments.no_album_title_tag or config.getboolean("DEFAULT", "no_album_title_tag", fallback=False),
            'no_track_artist_tag': arguments.no_track_artist_tag or config.getboolean("DEFAULT", "no_track_artist_tag", fallback=False),
            'no_track_title_tag': arguments.no_track_title_tag or config.getboolean("DEFAULT", "no_track_title_tag", fallback=False),
            'no_release_date_tag': arguments.no_release_date_tag or config.getboolean("DEFAULT", "no_release_date_tag", fallback=False),
            'no_media_type_tag': arguments.no_media_type_tag or config.getboolean("DEFAULT", "no_media_type_tag", fallback=False),
            'no_genre_tag': arguments.no_genre_tag or config.getboolean("DEFAULT", "no_genre_tag", fallback=False),
            'no_track_number_tag': arguments.no_track_number_tag or config.getboolean("DEFAULT", "no_track_number_tag", fallback=False),
            'no_track_total_tag': arguments.no_track_total_tag or config.getboolean("DEFAULT", "no_track_total_tag", fallback=False),
            'no_disc_number_tag': arguments.no_disc_number_tag or config.getboolean("DEFAULT", "no_disc_number_tag", fallback=False),
            'no_disc_total_tag': arguments.no_disc_total_tag or config.getboolean("DEFAULT", "no_disc_total_tag", fallback=False),
            'no_composer_tag': arguments.no_composer_tag or config.getboolean("DEFAULT", "no_composer_tag", fallback=False),
            'no_explicit_tag': arguments.no_explicit_tag or config.getboolean("DEFAULT", "no_explicit_tag", fallback=False),
            'no_copyright_tag': arguments.no_copyright_tag or config.getboolean("DEFAULT", "no_copyright_tag", fallback=False),
            'no_label_tag': arguments.no_label_tag or config.getboolean("DEFAULT", "no_label_tag", fallback=False),
            'no_upc_tag': arguments.no_upc_tag or config.getboolean("DEFAULT", "no_upc_tag", fallback=False),
            'no_isrc_tag': arguments.no_isrc_tag or config.getboolean("DEFAULT", "no_isrc_tag", fallback=False),
            
            # Add parallel download thread count configuration
            'max_workers': arguments.max_workers or config.get("DEFAULT", "max_workers", fallback="3"),

            # user_auth_token
            'user_auth_token': config.get("DEFAULT", "user_auth_token", fallback=""),
        }
        
        return QobuzDLSettings(**kwargs)