from qobuz_dl.constants import DEFAULT_FOLDER, DEFAULT_TRACK, DEFAULT_MULTIPLE_DISC_TRACK

class QobuzDLSettings:
    """
    Central configuration object for Qobuz-DL Ultimate Edition.
    
    Maps and stores all user preferences, CLI flags, and config.ini variables. 
    This object dictates the behavior of the Downloader, Tagger, and Sync engines, 
    enforcing the 'Zero Hardcoding' philosophy across the entire application.
    """
    
    def __init__(self, **kwargs):
        """
        Initializes the configuration settings.
        
        Args:
            **kwargs: Arbitrary keyword arguments containing all parsed configuration 
                values (e.g., tagging flags, folder formats, thread counts).
        """
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
        self.no_conductor_tag = kwargs.get('no_conductor_tag', False)
        self.no_ensemble_tag = kwargs.get('no_ensemble_tag', False)
        self.no_work_tag = kwargs.get('no_work_tag', False)
        self.no_explicit_tag = kwargs.get('no_explicit_tag', False)
        self.no_copyright_tag = kwargs.get('no_copyright_tag', False)
        self.no_label_tag = kwargs.get('no_label_tag', False)
        self.no_upc_tag = kwargs.get('no_upc_tag', False)
        self.no_isrc_tag = kwargs.get('no_isrc_tag', False)
        self.no_replaygain_tag = kwargs.get('no_replaygain_tag', False)
        self.no_album_url_tag = kwargs.get('no_album_url_tag', False)
        self.lrc_files = kwargs.get('lrc_files', True)
        self.embed_lyrics = kwargs.get('embed_lyrics', True)
        self.multi_value_tags = kwargs.get('multi_value_tags', False)

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
        """
        Factory method to construct a QobuzDLSettings object by merging command-line 
        arguments with the config.ini file. CLI arguments inherently take precedence 
        over config.ini values.
        
        Args:
            arguments (argparse.Namespace): Parsed command line arguments from the CLI.
            config (configparser.ConfigParser): The initialized ConfigParser object.
            
        Returns:
            QobuzDLSettings: The fully resolved configuration object.
        """
        # Determine the correct section to read from config.ini
        section = "qobuz" if config.has_section("qobuz") else "DEFAULT"
        
        # basic options
        kwargs = {
            'email': config.get(section, "email", fallback=""),
            'password': config.get(section, "password", fallback=""),
            'default_folder': arguments.directory or config.get(section, "default_folder", fallback="QobuzDownloads"),
            'default_quality': arguments.quality or config.get(section, "default_quality", fallback="6"),
            'default_limit': config.get(section, "default_limit", fallback="20"),
            'no_m3u': arguments.no_m3u or config.getboolean(section, "no_m3u", fallback=False),
            'albums_only': arguments.albums_only or config.getboolean(section, "albums_only", fallback=False),
            'no_fallback': arguments.no_fallback or config.getboolean(section, "no_fallback", fallback=False),
            'no_database': arguments.no_db or config.getboolean(section, "no_database", fallback=False),
            'app_id': config.get(section, "app_id", fallback=""),
            'secrets': [s for s in config.get(section, "secrets", fallback="").split(",") if s],
            'folder_format': arguments.folder_format or config.get(section, "folder_format", fallback=DEFAULT_FOLDER),
            'fallback_folder_format': arguments.fallback_folder_format or config.get(section, "fallback_folder_format", fallback=DEFAULT_FOLDER),
            'track_format': arguments.track_format or config.get(section, "track_format", fallback=DEFAULT_TRACK),
            'smart_discography': arguments.smart_discography or config.getboolean(section, "smart_discography", fallback=False),
            
            # cover options
            'embed_art': arguments.embed_art or config.getboolean(section, "embed_art", fallback=True),
            'og_cover': arguments.og_cover or config.getboolean(section, "og_cover", fallback=False),
            'no_cover': arguments.no_cover or config.getboolean(section, "no_cover", fallback=False),
            'embedded_art_size': arguments.embedded_art_size or config.get(section, "embedded_art_size", fallback="600"),
            'saved_art_size': arguments.saved_art_size or config.get(section, "saved_art_size", fallback="org"),
            
            # multiple disc option
            'multiple_disc_prefix': arguments.multiple_disc_prefix or config.get(section, "multiple_disc_prefix", fallback="CD"),
            'multiple_disc_one_dir': arguments.multiple_disc_one_dir or config.getboolean(section, "multiple_disc_one_dir", fallback=False),
            'multiple_disc_track_format': arguments.multiple_disc_track_format or config.get(section, "multiple_disc_track_format", fallback="{disc_number}.{track_number} - {track_title}"),
                                 
            # tag options
            'no_album_artist_tag': arguments.no_album_artist_tag or config.getboolean(section, "no_album_artist_tag", fallback=False),
            'no_album_title_tag': arguments.no_album_title_tag or config.getboolean(section, "no_album_title_tag", fallback=False),
            'no_track_artist_tag': arguments.no_track_artist_tag or config.getboolean(section, "no_track_artist_tag", fallback=False),
            'no_track_title_tag': arguments.no_track_title_tag or config.getboolean(section, "no_track_title_tag", fallback=False),
            'no_release_date_tag': arguments.no_release_date_tag or config.getboolean(section, "no_release_date_tag", fallback=False),
            'no_media_type_tag': arguments.no_media_type_tag or config.getboolean(section, "no_media_type_tag", fallback=False),
            'no_genre_tag': arguments.no_genre_tag or config.getboolean(section, "no_genre_tag", fallback=False),
            'no_track_number_tag': arguments.no_track_number_tag or config.getboolean(section, "no_track_number_tag", fallback=False),
            'no_track_total_tag': arguments.no_track_total_tag or config.getboolean(section, "no_track_total_tag", fallback=False),
            'no_disc_number_tag': arguments.no_disc_number_tag or config.getboolean(section, "no_disc_number_tag", fallback=False),
            'no_disc_total_tag': arguments.no_disc_total_tag or config.getboolean(section, "no_disc_total_tag", fallback=False),
            'no_composer_tag': arguments.no_composer_tag or config.getboolean(section, "no_composer_tag", fallback=False),
            'no_conductor_tag': getattr(arguments, 'no_conductor_tag', False) or config.getboolean(section, "no_conductor_tag", fallback=False),
            'no_ensemble_tag': getattr(arguments, 'no_ensemble_tag', False) or config.getboolean(section, "no_ensemble_tag", fallback=False),
            'no_work_tag': getattr(arguments, 'no_work_tag', False) or config.getboolean(section, "no_work_tag", fallback=False),
            'no_explicit_tag': arguments.no_explicit_tag or config.getboolean(section, "no_explicit_tag", fallback=False),
            'no_copyright_tag': arguments.no_copyright_tag or config.getboolean(section, "no_copyright_tag", fallback=False),
            'no_label_tag': arguments.no_label_tag or config.getboolean(section, "no_label_tag", fallback=False),
            'no_upc_tag': arguments.no_upc_tag or config.getboolean(section, "no_upc_tag", fallback=False),
            'no_isrc_tag': arguments.no_isrc_tag or config.getboolean(section, "no_isrc_tag", fallback=False),
            'no_replaygain_tag': getattr(arguments, 'no_replaygain_tag', False) or config.getboolean(section, "no_replaygain_tag", fallback=False),
            'no_album_url_tag': getattr(arguments, 'no_album_url_tag', False) or config.getboolean(section, "no_album_url_tag", fallback=False),
            
            # Add parallel download thread count configuration
            'max_workers': arguments.max_workers or config.get(section, "max_workers", fallback="3"),

            # user_auth_token
            'user_auth_token': config.get(section, "user_auth_token", fallback=""),
        
            'lrc_files': not getattr(arguments, 'no_lrc_files', config.getboolean(section, "no_lrc_files", fallback=False)),
        
            'embed_lyrics': False if getattr(arguments, 'no_embed_lyrics', False) else config.getboolean(section, "embed_lyrics", fallback=True),
        
            'multi_value_tags': getattr(arguments, 'multi_value_tags', config.getboolean(section, "multi_value_tags", fallback=False)),
        }
        
        return QobuzDLSettings(**kwargs)