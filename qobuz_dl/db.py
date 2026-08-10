import logging
import sqlite3

from qobuz_dl.color import YELLOW, RED, OFF

logger = logging.getLogger(__name__)


def create_db(db_path):
    """
    Initializes or upgrades the SQLite database used for the Smart Reverse Lookup feature.

    Handles legacy migrations (e.g., v1 to v2, adding quality/format columns) 
    and recent schema upgrades (e.g., adding artist and album columns).

    Args:
        db_path (str): The file path where the SQLite database is or will be stored.

    Returns:
        str: The path to the successfully initialized database.
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Check if the table already exists
        cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='downloads'")
        
        if cursor.fetchone()[0] == 1:
            # Table exists. Read current columns
            cursor.execute("PRAGMA table_info(downloads)")
            columns = [info[1] for info in cursor.fetchall()]
            
            # Legacy migration (v1 to v2)
            if 'quality' not in columns:
                logger.info(f"{YELLOW}Migrating old database to the new format...{OFF}")
                
                # Rename the old table
                conn.execute("ALTER TABLE downloads RENAME TO downloads_old")
                
                # Create the new table with updated schema including artist and album
                conn.execute("""
                CREATE TABLE downloads (
                  "id" text NOT NULL,
                  "media_type" text NOT NULL DEFAULT 'album',
                  "quality" integer NOT NULL DEFAULT 27,
                  "file_format" text NOT NULL DEFAULT 'FLAC',
                  "quality_met" integer NOT NULL DEFAULT 0,
                  "bit_depth" text,
                  "sampling_rate" text,
                  "saved_path" text NOT NULL DEFAULT '',
                  "status" text NOT NULL DEFAULT 'downloaded',
                  "url" text NOT NULL DEFAULT '',
                  "release_date" text NOT NULL DEFAULT '',
                  "artist" text NOT NULL DEFAULT '',
                  "album" text NOT NULL DEFAULT '',
                  PRIMARY KEY ("id", "quality")
                );
                """)
                
                # Copy old historical IDs
                try:
                    conn.execute("INSERT INTO downloads (id) SELECT id FROM downloads_old")
                except sqlite3.Error as e:
                    logger.error(f"{RED}Failed to migrate old data: {e}{OFF}")
                
                # Drop the temporary old table
                conn.execute("DROP TABLE downloads_old")
                logger.info(f"{YELLOW}Database successfully updated!{OFF}")
                
            # New Migration (v2 to v2.1.4): Add artist and album if missing
            elif 'artist' not in columns:
                logger.info(f"{YELLOW}Upgrading database schema: Adding artist and album columns...{OFF}")
                try:
                    conn.execute("ALTER TABLE downloads ADD COLUMN artist text NOT NULL DEFAULT ''")
                    conn.execute("ALTER TABLE downloads ADD COLUMN album text NOT NULL DEFAULT ''")
                    logger.info(f"{YELLOW}Schema upgrade complete!{OFF}")
                except sqlite3.Error as e:
                    logger.error(f"{RED}Failed to add new columns: {e}{OFF}")
                
        else:
            # Table does not exist, create it from scratch
            try:
                conn.execute("""
                CREATE TABLE downloads (
                  "id" text NOT NULL,
                  "media_type" text NOT NULL DEFAULT 'album',
                  "quality" integer NOT NULL DEFAULT 27,
                  "file_format" text NOT NULL DEFAULT 'FLAC',
                  "quality_met" integer NOT NULL DEFAULT 0,
                  "bit_depth" text,
                  "sampling_rate" text,
                  "saved_path" text NOT NULL DEFAULT '',
                  "status" text NOT NULL DEFAULT 'downloaded',
                  "url" text NOT NULL DEFAULT '',
                  "release_date" text NOT NULL DEFAULT '',
                  "artist" text NOT NULL DEFAULT '',
                  "album" text NOT NULL DEFAULT '',
                  PRIMARY KEY ("id", "quality")
                );
                """)
                logger.info(f"{YELLOW}Download-IDs database created{OFF}")
            except sqlite3.OperationalError:
                pass
                
        return db_path


def handle_download_id(db_path, item_id, add_id=False, media_type='album', quality=27, file_format='FLAC',
                       quality_met=0, bit_depth=None, sampling_rate=None, saved_path='', status='downloaded',
                       url='', release_date='', artist='', album=''):
    """
    Checks for existing downloads or inserts new completed downloads into the database.

    Args:
        db_path (str): The file path to the SQLite database.
        item_id (str): The unique Qobuz ID of the track or album.
        add_id (bool, optional): If True, inserts a new record. If False, queries for existence. Defaults to False.
        media_type (str, optional): 'album' or 'track'. Defaults to 'album'.
        quality (int, optional): The requested audio quality ID. Defaults to 27.
        file_format (str, optional): The actual downloaded format (e.g., 'FLAC', 'MP3'). Defaults to 'FLAC'.
        quality_met (int, optional): Flag indicating if the requested quality was achieved (1 or 0). Defaults to 0.
        bit_depth (str, optional): Audio bit depth. Defaults to None.
        sampling_rate (str, optional): Audio sampling rate. Defaults to None.
        saved_path (str, optional): The local file system path where the item was saved. Defaults to ''.
        status (str, optional): The download status. Defaults to 'downloaded'.
        url (str, optional): The original Qobuz URL. Defaults to ''.
        release_date (str, optional): The item's release date. Defaults to ''.
        artist (str, optional): The main artist's name. Defaults to ''.
        album (str, optional): The album's title. Defaults to ''.

    Returns:
        tuple or None: If add_id is False, returns a tuple containing the ID if found, otherwise None.
    """
    if not db_path:
        return

    with sqlite3.connect(db_path) as conn:
        if add_id:
            try:
                # Inject artist and album dynamically into the database
                conn.execute(
                    """
                    INSERT INTO downloads (id, media_type, quality, file_format, quality_met, bit_depth, 
                    sampling_rate, saved_path, url, release_date, status, artist, album) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (item_id, media_type, quality, file_format, quality_met, bit_depth, sampling_rate,
                     saved_path, url, release_date, status, artist, album),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                # Provide clean visual feedback instead of an error
                logger.info(f"{YELLOW}[i] Already in database, skipping.{OFF}")
            except sqlite3.Error as e:
                logger.error(f"{RED}Unexpected DB error: {e}{OFF}")
        else:
            return conn.execute(
                "SELECT id FROM downloads WHERE id=? AND quality=?",
                (item_id, quality),
            ).fetchone()
 
 
def get_stats(db_path):
    """
    Retrieves statistical information from the database, specifically a list of unique downloaded artists.

    Args:
        db_path (str): The file path to the SQLite database.

    Returns:
        list: A sorted list of unique artist names present in the database. Returns an empty list on failure.
    """
    if not db_path:
        return []
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # We select unique artists, excluding empty strings
            cursor.execute("SELECT DISTINCT artist FROM downloads WHERE artist != '' ORDER BY artist ASC")
            return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error:
        return []