# Beets
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.library import Item
from beets import config

from .SpotifyPlugin import spotify_plugin
from .YoutubePlugin import youtube_plugin

# Varia
import logging
import datetime


class PlatformManager(BeetsPlugin):
    
    def __init__(self):

        # self.sf = SpotifyPlugin()
        # self.yt = YouTubePlugin()

        super().__init__()
        self._log = logging.getLogger('beets.platform_manager')

        # Central command definitions
        self.add_command = Subcommand('add', help='Add tracks to a playlist on a specified platform')
        self.add_command.parser.add_option('--platform', dest='platform', choices=['spotify', 'youtube', 'sf', 'yt'], help='Specify the music platform (spotify, youtube)')
        self.add_command.parser.add_option('-p', '--playlist', dest='playlist', help='Playlist name or ID')
        self.add_command.parser.add_option('-s', '--songs', dest='songs', help='List of song dictionaries')
        self.add_command.func = self.add_to_playlist

        self.retrieve_command = Subcommand('retrieve', help='Retrieve playlists and their tracks from a specified platform')
        self.retrieve_command.parser.add_option('--platform', dest='platform', choices=['spotify', 'youtube', 'sf', 'yt'], help='Specify the music platform (spotify, youtube)')
        self.retrieve_command.parser.add_option('--type', dest='playlist_type', choices=['pl', 'mm'], default=None, help="Process 'pl' playlists or regular genre/subgenre playlists")
        self.retrieve_command.parser.add_option('--no-db', action='store_true', help='Do not add retrieved info to the database')
        self.retrieve_command.parser.add_option('--name', dest='playlist_name', help='Name of the playlist to retrieve')
        self.retrieve_command.func = self.retrieve_info

    def commands(self):
        return [self.add_command, self.retrieve_command]

    def setup(self, lib):
        self.lib = lib
        with self.lib.transaction() as tx:
            tx.query("""
            CREATE TABLE IF NOT EXISTS playlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                spotify_id TEXT,
                youtube_id TEXT,
                path TEXT,
                last_edited_at DATE,
                type TEXT
            );
            """)
            tx.query("""
            CREATE TABLE IF NOT EXISTS playlist_item (
                playlist_id INTEGER,
                item_id INTEGER,
                FOREIGN KEY (playlist_id) REFERENCES playlist(id),
                FOREIGN KEY (item_id) REFERENCES items(id),
                PRIMARY KEY (playlist_id, item_id)
            );
            """)

    # COMMAND PARSER

    def add_to_playlist(self, lib, opts, args):
        """Handle add command and dispatch to the correct platform plugin."""
        platform = opts.platform
        playlist = opts.playlist
        songs = opts.songs

        plugin = self.get_plugin_for_platform(platform)
        plugin.add_to_playlist(playlist, songs)

    def retrieve_info(self, lib, opts, args):
        """Handle retrieve command and dispatch to the correct platform plugin."""
        platform = opts.platform
        playlist_name = opts.playlist_name
        playlist_type = opts.playlist_type
        no_db = opts.no_db

        plugin = self.get_plugin_for_platform(platform)

        with plugin() as p:
            p.retrieve_info(lib, playlist_name=playlist_name, playlist_type=playlist_type, no_db=no_db)

    def get_plugin_for_platform(self, platform):
        """Return the appropriate plugin class based on the platform."""
        if platform == ('sf' or 'spotify') :
            return spotify_plugin
        elif platform == ('yt' or 'youtube'):
            return youtube_plugin
        else:
            raise ValueError(f"Unsupported platform: {platform}")


    # DATABASE METHODS

    def _find_item(self, lib, song):
        title = song['title']
        artist = ' '.join(song['main_artist'])
        remix_artist = song.get('remix_artist', '')
        remix_type = song.get('remix_type', '')

        query_str = f"title:{title} main_artist:{artist} remix_artist:{remix_artist} remix_type:{remix_type}".replace("'", "\\'")

        try:
            query = lib.items(query_str)
        except Exception as e:
            self._log.error(f'Query error due to quotation issues: {e}')
            return None
        return query.get()

    def _store_item(self, lib, song, update_genre=False):
        item = self._find_item(lib, song)
        current_time = datetime.datetime.now().isoformat()

        # pop genre 
        genre = song.pop('genre', '')
        subgenre = song.pop('subgenre', '')

        if item:
            # Update existing item
            is_new = False
        else:
            # Create new item
            item = Item()
            item.title = song.pop('title')
            item.main_artist = song.pop('main_artist')
            is_new = True

        item_fields = Item._fields.keys()
        for key, value in song.items():
            if value and key in item_fields:
                setattr(item, key, value)
        
        item.last_edited = current_time

        if update_genre:
            item.genre = genre if genre else item.genre
            item.subgenre = subgenre if subgenre else item.subgenre

        if is_new:
            lib.add(item)
        
        item.store()
        return item.id
    
    def _find_playlist(self, lib, playlist_name):
        with lib.transaction() as tx:
            result = tx.query("SELECT * FROM playlist WHERE name = ?", (playlist_name,))
            # row = result.fetchone()
            return result[0] if result else None
    
    def _store_playlist(self, lib, playlist):
        existing_playlist = self._find_playlist(lib, playlist['name'])
        current_time = datetime.datetime.now().isoformat()
        with lib.transaction() as tx:
            if existing_playlist:
                # Update existing playlist
                tx.query("""
                    UPDATE playlist SET description = ?, spotify_id = ?, youtube_id = ?, path = ?, last_edited_at = ?, type = ?
                    WHERE id = ?
                """, (playlist.get('description', ''), '', playlist['youtube_id'], '', current_time, 'playlist', existing_playlist['id']))
                return existing_playlist['id']
            else:
                # Create new playlist
                tx.query("""
                    INSERT INTO playlist (name, description, spotify_id, youtube_id, path, last_edited_at, type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (playlist['name'], playlist.get('description', ''), '', playlist['spotify_id'], '', current_time, 'playlist'))
                return lib._connection().lastrowid
       
    def _store_playlist_relation(self, lib, item_id, playlist_id):
        with lib.transaction() as tx:
            tx.query("""
                INSERT OR IGNORE INTO playlist_item (playlist_id, item_id)
                VALUES (?, ?)
            """, (playlist_id, item_id))

