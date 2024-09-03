
# # plugin = SpotifyCustomPlugin()
# ========================================================================================
# ########################################################################################
# ========================================================================================

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.library import Item
import logging
from typing import List, Dict
import datetime
import re
from beets import config
from beets.dbcore.types import String

class SpotifyCustomPlugin(BeetsPlugin):

    def __init__(self):
        super(SpotifyCustomPlugin, self).__init__()





        self.config.add({
            'client_id': '',
            'client_secret': '',
            'redirect_uri': 'http://localhost:8888/callback'
        })

        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=self.config['client_id'].get(),
            client_secret=self.config['client_secret'].get(),
            redirect_uri=self.config['redirect_uri'].get(),
            scope="playlist-read-private playlist-modify-private playlist-modify-public"
        ))

        self._log = logging.getLogger('beets.spotify_custom')

        # Define subcommands
        self.add_command = Subcommand('playlists_add_sf', help='Add tracks to a Spotify playlist')
        self.add_command.parser.add_option('-p', '--playlist', dest='playlist', help='Playlist name or ID')
        self.add_command.parser.add_option('-s', '--songs', dest='songs', help='List of song dictionaries')
        self.add_command.func = self.add_to_playlist

        self.retrieve_command = Subcommand('retrieve_sf', help='Retrieve all playlists and their tracks')
        self.retrieve_command.parser.add_option('--type', dest='playlist_type', choices=['pl', 'mm'], default='mm', help="process 'pl' playlists or regular genre/subgenre playlists")
        self.retrieve_command.parser.add_option('--no-db', action='store_true', help='Do not add retrieved info to the database')
        self.retrieve_command.parser.add_option('-n', '--playlist-name', dest='playlist_name', help='Name of the playlist to retrieve')
        self.retrieve_command.func = self.retrieve_info

        self.register_listener('library_opened', self.setup)

    def commands(self):
        return [self.add_command, self.retrieve_command]

    def setup(self, lib):
        self.lib = lib

        columns = [("main_artist", "TEXT")]

        with self.lib.transaction() as tx:
            tx.query("""
            CREATE TABLE IF NOT EXISTS playlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                spotify_id TEXT,
                youtube_id TEXT,
                soundcloud_id TEXT,
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


    
    # GET PLAYLIST INFO FROM API
    
    def retrieve_info(self, lib, opts, args):
        # CLI arguments
        no_db = opts.no_db
        playlist_name = opts.playlist_name
        playlist_type = opts.playlist_type

        # Get playlists to process
        all_playlists = self._get_all_playlists()
        playlists_to_process = [playlist for playlist in all_playlists if not playlist_name or playlist['playlist_name'] == playlist_name]
        playlists_to_process = [pl for pl in playlists_to_process if ' pl ' in pl['playlist_name']] if playlist_type=='pl' else [pl for pl in playlists_to_process if ' pl ' not in pl['playlist_name'] 
                                                                                                                            and 'mm -' in pl['playlist_name']
                                                                                                                            and pl['playlist_name'] not in str(self.config['pl_to_skip']).split(',')]
        
        print("PROCESSING")
        for pl in playlists_to_process:
            print(pl['playlist_name'])

        for playlist in playlists_to_process:
            # get playlist from spotify API
            playlist_name = playlist['playlist_name']
            # process playlist if it exists
            if playlist:
                # get all tracks
                tracks = self.sp.playlist_tracks(playlist['spotify_id'])
                self._log.info(f"Retrieved playlist '{playlist['playlist_name']}' with {len(tracks['items'])} songs.")
                for item in tracks['items']:
                    # create song data object from parsing track items
                    song_data = self._parse_track_item(item)
                    self._log.info(f" {song_data['artists']} - {song_data['title']} {song_data['remix_artist']} {song_data['remix_type']}")

                    song_data['playlist_name'] = playlist_name
                    song_data['playlist_id'] = playlist['spotify_id']


                    # DATABASE 
                    if not no_db:
                        # UPSERT SONG
                        song_id = self._store_item(lib, song_data, update_genre=True)
                        # UPSERT PLAYLIST
                        playlist_id = self._store_playlist(lib, playlist)
                        # PLAYLIST_ITEM  RELATION
                        self._store_playlist_relation(lib, song_id, playlist_id)
            else:
                print(f"Playlist '{playlist_name}' not found.")
                self._log.info(f"Playlist '{playlist_name}' not found.")
    

    def _get_all_playlists(self) -> List[Dict[str, str]]:
        playlists = []
        offset = 0
        limit = 50
        while True:
            results = self.sp.current_user_playlists(limit=limit, offset=offset)
            playlists.extend(results['items'])
            if results['next'] is None:
                break
            offset += limit
        return [{'playlist_name': p['name'], 'spotify_id': p['id']} for p in playlists]
    
    def get_playlist_by_name(self, name):
        playlists = self._get_all_playlists()
        for playlist in playlists:
            if playlist['name'].lower() == name.lower():
                return playlist
        return None
    
    def _parse_track_item(self, item) -> Dict:
        song_data = dict()
        track = item['track']
        print(track['name'])
        # title
        title = track['name'].split(' - ')[0]

        # ARTISTS
        artists = [artist['name'] for artist in track['artists']]
        # main 
        main_artist = artists[0]
        # feat 
        _ = re.search(r'\(feat\. (.*?)\)', title)
        feat_artist, title = (_.group(1).strip(), title[:_.start()] + title[_.end():].strip()) if _ else ('', title)
        if feat_artist:
            artists += [feat_artist]
        # remix 
        remix_artist = track['name'].split(' - ')[1].replace(' Remix', '') if len(track['name'].split(' - ')) > 1 else ''
        if remix_artist:
            artists += [remix_artist]
        # remove duplicates and substrings
        substrings = {a for a in artists for other in artists if a != other and a in other}
        artists = [a for a in artists if a not in substrings]
        # sort
        artists = sorted(artists)
            
    # Filter out strings that are substrings of any other string
        # spotify id
        spotify_id = track['id']
        # populate dict
        song_data['artists'] = artists
        song_data['title'] = title
        song_data['remix_artist'] = remix_artist
        song_data['remix_type'] = 'Remix' if remix_artist else ''
        song_data['spotify_id'] = spotify_id
        song_data['feat_artist'] = feat_artist
        song_data['main_artist'] = main_artist

        return song_data
    
    # DATABASE STUFF
    
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
            item.genre = genre if genre else (item.genre if 'genre' in item_fields else '')
            item.subgenre = subgenre if subgenre else (item.subgenre if 'subgenre' in item_fields else '')

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
        existing_playlist = self._find_playlist(lib, playlist['playlist_name'])
        current_time = datetime.datetime.now().isoformat()
        with lib.transaction() as tx:
            if existing_playlist:
                # Update existing playlist
                tx.query("""
                    UPDATE playlist SET description = ?, spotify_id = ?, youtube_id = ?, path = ?, last_edited_at = ?, type = ?
                    WHERE id = ?
                """, (playlist.get('description', ''), playlist['spotify_id'], '', '', current_time, 'playlist', existing_playlist['id']))
                return existing_playlist['id']
            else:
                # Create new playlist
                tx.query("""
                    INSERT INTO playlist (name, description, spotify_id, youtube_id, path, last_edited_at, type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (playlist['playlist_name'], playlist.get('description', ''), playlist['spotify_id'], '', '', current_time, 'playlist'))
        
        existing_playlist = self._find_playlist(lib, playlist['playlist_name'])
        return existing_playlist['id']
       
    def _store_playlist_relation(self, lib, item_id, playlist_id):
        with lib.transaction() as tx:
            tx.query("""
                INSERT OR IGNORE INTO playlist_item (playlist_id, item_id)
                VALUES (?, ?)
            """, (playlist_id, item_id))
    
    
    


    

    # SEARCH API
    
    def build_query(self, song):
        query_parts = []
        if 'artists' in song:
            query_parts.append(f"artist:{' '.join(song['artists'])}")
        if 'title' in song:
            query_parts.append(f"track:{song['title']}")
        if 'remix_artist' in song:
            query_parts.append(f"remixer:{song['remix_artist']}")
        if 'remix_type' in song:
            query_parts.append(f"remix:{song['remix_type']}")
        return ' '.join(query_parts)

    def search_spotify(self, query):
        results = self.sp.search(q=query, type='track', limit=10)
        tracks = results['tracks']['items']
        best_match = None
        best_score = 0
        for track in tracks:
            score = self.calculate_match_score(track, query)
            if score > best_score:
                best_match = track['id']
                best_score = score
        return best_match

    
    # MATCHING
    
    def calculate_match_score(self, track, query):
        score = 0
        if query.lower() in track['name'].lower():
            score += 1
        if any(artist['name'].lower() in query.lower() for artist in track['artists']):
            score += 1
        return score



    # UPDATE API

    def add_items_to_library(self, lib, items_to_add):
        lib.add(items_to_add)
        lib.save()
        for item in items_to_add:
            item.store()

    def add_to_playlist(self, lib, opts, args):
        playlist_name_or_id = opts.playlist
        song_dicts = eval(opts.songs)  # Use a safer parsing method in production

        playlists = self.get_all_playlists()
        spotify_id = None
        for playlist in playlists:
            if playlist['name'] == playlist_name_or_id or playlist['spotify_id'] == playlist_name_or_id:
                spotify_id = playlist['spotify_id']
                break

        if not spotify_id:
            user_id = self.sp.current_user()['id']
            playlist = self.sp.user_playlist_create(user_id, playlist_name_or_id)
            spotify_id = playlist['id']
            self.store_playlist_info(lib, playlist)

        successful_adds = []
        failed_adds = []
        items_to_add = []

        for song in song_dicts:
            query = self.build_query(song)
            track_id = self.search_spotify(query)
            if track_id:
                successful_adds.append((song, track_id))
                item = Item(title=song['title'], artist=' '.join(song['artists']))
                items_to_add.append(item)
            else:
                failed_adds.append(song['title'])

        if items_to_add:
            self.add_items_to_library(lib, items_to_add)
            internal_playlist_id = self.get_internal_playlist_id(lib, spotify_id=spotify_id)
            for item, (song, track_id) in zip(items_to_add, successful_adds):
                self.store_track_info(lib, song)  # Add this line
                internal_track_id = self.get_internal_track_id(lib, track_id)  # Fetch internal track ID
                self.store_playlist_relation(lib, internal_track_id, internal_playlist_id)

        if successful_adds:
            self.sp.playlist_add_items(spotify_id, [track_id for _, track_id in successful_adds])

        self._log.info(f"Added {len(successful_adds)} tracks to playlist '{playlist_name_or_id}'. Failed to add: {', '.join(failed_adds) if failed_adds else 'None'}")
        print(f"Successfully added {len(successful_adds)} tracks to playlist {playlist_name_or_id}.")
        if failed_adds:
            print(f"Failed to find the following tracks: {', '.join(failed_adds)}")