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
from functools import wraps
from typing import List, Dict

class PlatformManager(BeetsPlugin):
    
    def __init__(self):

        super().__init__()
        self._log = logging.getLogger('beets.platform_manager')

        # Central command definitions
        self.add_command = Subcommand('add', help='Add tracks to a playlist on a specified platform')
        self.add_command.parser.add_option('--platform', dest='platform', choices=['spotify', 'youtube', 'sf', 'yt'], help='Specify the music platform (spotify, youtube)')
        self.add_command.parser.add_option('-p', '--playlist', dest='playlist', help='Playlist name or ID')
        self.add_command.parser.add_option('-s', '--songs', dest='songs', help='List of song dictionaries')
        self.add_command.func = self.add_to_playlist

        self.pull_command = Subcommand('pull')
        self.pull_command.parser.add_option('--platform', dest='platform', choices=['all', 'spotify', 'youtube', 'a'], help='Specify the music platform (spotify, youtube)')
        self.pull_command.parser.add_option('--type', dest='playlist_type', choices=['pl', 'mm'], default=None, help="Process 'pl' playlists or regular genre/subgenre playlists")
        self.pull_command.parser.add_option('--no-db', action='store_true', help='Do not add retrieved info to the database')
        self.pull_command.parser.add_option('--name', dest='playlist_name', help='Name of the playlist to retrieve')
        self.pull_command.func = self.pull_platform

    def commands(self):
        return [self.add_command, self.pull_command]

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

    # MEAT

    def add_to_playlist(self, lib, opts, args):
        """Handle add command and dispatch to the correct platform plugin."""
        platform = opts.platform
        playlist = opts.playlist
        songs = opts.songs

        plugin = self.get_plugin_for_platform(platform)
        plugin.add_to_playlist(playlist, songs)

    def pull_platform(self, lib, opts, args):
        songs = list()

        # GET ARGUMENTS
        platform = opts.platform
        playlist_name = opts.playlist_name
        playlist_type = opts.playlist_type
        no_db = opts.no_db
        
        # PLATFORMS TO PULL FROM
        platforms = ['youtube', 'spotify'] if platform == ('a' or 'all') else [platform]

        # GET SONGS
        for platform in platforms:
            songs += self._retrieve_songs(platform, playlist_name, playlist_type)

        if not no_db:
            self._insert_songs(lib, songs)
        
        return
    
    def _retrieve_songs(self, platform, playlist_name=None, playlist_type=None) -> List[Dict]:
        """Handle retrieve command and dispatch to the correct platform plugin."""
        
        songs = list()

        # GET PLUGIN
        p = self._get_plugin_for_platform(platform)

        with p() as plugin:
            # get playlists to process based on filters
            playlists_to_process = self._get_playlists(plugin, playlist_name, playlist_type)
            for playlist in playlists_to_process:
                playlist_name = playlist['playlist_name']
                if playlist:
                    # Get tracks
                    tracks = plugin._get_playlist_tracks(playlist['playlist_id'])
                    
                    print(tracks.keys())

                    # parse tracks
                    for item in tracks['items']:
                        song_data = plugin._parse_track_item(item)
                        self._log.debug(f" {song_data['artists']} - {song_data['title']} {song_data['remix_artist']} {song_data['remix_type']}")
                        
                        # add playlist info to track dict
                        song_data['platform'] = platform
                        song_data['playlist_name'] = playlist_name
                        song_data['playlist_id'] = playlist['playlist_id']
                        song_data['playlist_description'] = playlist['playlist_description']
                        
                        # add genre data based on playlist name
                        if ' pl ' not in playlist_name:
                            playlist_split = playlist['playlist_name'].split(' - ')
                            if len(playlist_split) > 2:
                                _, genre, subgenre = playlist_split
                                song_data['genre'] = genre
                                song_data['subgenre'] = subgenre
                            else:
                                _, genre = playlist_split
                                song_data['genre'] = genre
                                song_data['subgenre'] = ''
                        else:
                                song_data['genre'] = ''
                                song_data['subgenre'] = ''
                        
                        songs.append(song_data)
        return songs
        
    def _insert_songs(self, lib, songs) -> List[Item]:
        items = list()
        for song_data in songs:
            platform = song_data.pop('platform')
            p = {key: song_data.pop(key) for key in ['playlist_id', 'playlist_name', 'playlist_description'] if key in song_data}
            
            # UPSERT SONG      
            item = self._store_item(lib, song_data, update_genre=True)

            # UPSERT PLAYLIST
            playlist = self._store_playlist(lib, platform, p)
            # PLAYLIST_ITEM  RELATION
            self._store_playlist_relation(lib, item.id, playlist['id'])    
        return items

    # HELPER

    def _get_plugin_for_platform(self, platform):
        print(platform)
        """Return the appropriate plugin class based on the platform."""
        if platform == 'spotify' :
            return spotify_plugin
        elif platform == 'youtube':
            return youtube_plugin
        else:
            raise ValueError(f"Unsupported platform: {platform}")

    def _get_playlists(self, plugin, playlist_name, playlist_type) -> List[Dict]:
        # FILTER PLAYLISTS
        # all
        all_playlists = plugin._get_all_playlists()
        # filter mm playlists 
        playlists_to_process = [playlist for playlist in all_playlists if playlist['playlist_name'][:2] == plugin.valid_pl_prefix]
        # filter ignore
        playlists_to_process = [playlist for playlist in playlists_to_process if playlist['playlist_name'] not in plugin.pl_to_skip]                
        # filter type
        playlists_to_process = [playlist for playlist in playlists_to_process if playlist_type in playlist['playlist_name']] if playlist_type else playlists_to_process
        # filter name
        playlists_to_process = [playlist for playlist in playlists_to_process if playlist_name.lower() in playlist['playlist_name'].lower()] if playlist_name else playlists_to_process
        
        self._log.debug("PROCESSING")
        for pl in playlists_to_process:
            self._log.debug(pl['playlist_name'])

        return playlists_to_process
    
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

    def _find_playlist(self, lib, playlist_name):
        with lib.transaction() as tx:
            result = tx.query("SELECT * FROM playlist WHERE name = ?", (playlist_name,))
            return result[0] if result else None    
    
    def _store_item(self, lib, song_data, update_genre=True):

        song = song_data
        item = self._find_item(lib, song)
        current_time = datetime.datetime.now().isoformat()

        if item:
            # Update existing item
            is_new = False
        else:
            # Create new item
            item = Item()
            item.title = song.pop('title')
            item.main_artist = song.pop('main_artist')
            is_new = True


        # pop genre 
        genre = song.pop('genre', '')
        subgenre = song.pop('subgenre', '')
        if update_genre:
            if genre:
                item.genre = genre
            if subgenre:
                item.subgenre = subgenre
                

        item_fields = Item._fields.keys()

        for key, value in song_data.items():
            if key in item_fields and value:
                setattr(item, key, value)
        
        item.last_edited = current_time

        if is_new:
            lib.add(item)
        
        item.store()
        return item
    
    def _store_playlist(self, lib, platform, playlist):

        playlist_id = playlist['playlist_id']
        playlist_name = playlist['playlist_name']
        playlist_description = playlist['playlist_description']

        existing_playlist = self._find_playlist(lib, playlist_name)

        current_time = datetime.datetime.now().isoformat()

        if existing_playlist:
            spotify_id = existing_playlist['spotify_id']
            youtube_id = existing_playlist['youtube_id']
        else:
            spotify_id = playlist_id if platform == 'spotify' else ''
            youtube_id = playlist_id if platform == 'youtube' else ''   

        with lib.transaction() as tx:
            if existing_playlist:
                # Update existing playlist
                tx.query("""
                    UPDATE playlist SET description = ?, spotify_id = ?, youtube_id = ?, path = ?, last_edited_at = ?, type = ?
                    WHERE id = ?
                """, (playlist.get('playlist_description', ''), spotify_id, youtube_id, '', current_time, 'playlist', existing_playlist['id']))
                return existing_playlist
            else:
                # Create new playlist
                tx.query("""
                    INSERT INTO playlist (name, description, spotify_id, youtube_id, path, last_edited_at, type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (playlist['playlist_name'], playlist.get('playlist_description', ''), spotify_id, youtube_id, '', current_time, 'playlist'))
                
                existing_playlist = self._find_playlist(lib, playlist_name)
                return existing_playlist
       
    def _store_playlist_relation(self, lib, item_id, playlist_id):
        with lib.transaction() as tx:
            tx.query("""
                INSERT OR IGNORE INTO playlist_item (playlist_id, item_id)
                VALUES (?, ?)
            """, (playlist_id, item_id))

