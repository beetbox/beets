# import spotipy
# from spotipy.oauth2 import SpotifyOAuth
# from beets.plugins import BeetsPlugin
# from beets.ui import Subcommand
# from beets.library import Item, Album
# from beets import config
# import logging

# class SpotifyCustomPlugin(BeetsPlugin):

#     def __init__(self):
#         super(SpotifyCustomPlugin, self).__init__()

#         self.config.add({
#             'client_id': '',
#             'client_secret': '',
#             'redirect_uri': 'http://localhost:8888/callback',
#         })

#         self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
#             client_id=self.config['client_id'].get(),
#             client_secret=self.config['client_secret'].get(),
#             redirect_uri=self.config['redirect_uri'].get(),
#             scope="playlist-read-private playlist-modify-private playlist-modify-public"
#         ))

#         self._log = logging.getLogger('beets.spotify_custom')

#         # Define subcommands
#         self.add_command = Subcommand('add_to_playlist', help='Add tracks to a Spotify playlist')
#         self.add_command.parser.add_option('-p', '--playlist', dest='playlist', help='Playlist name or ID')
#         self.add_command.parser.add_option('-s', '--songs', dest='songs', help='List of song dictionaries')
#         self.add_command.func = self.add_to_playlist

#         self.retrieve_command = Subcommand('retrieve_playlists', help='Retrieve all playlists and their tracks')
#         self.retrieve_command.parser.add_option('--no-db', action='store_true', help='Do not add retrieved info to the database')
#         self.retrieve_command.parser.add_option('-n', '--playlist-name', dest='playlist_name', help='Name of the playlist to retrieve')
#         self.retrieve_command.func = self.retrieve_playlists

#     def commands(self):
#         return [self.add_command, self.retrieve_command]


#     def _parse_track(self, item) -> dict:
#         song_data = dict()
#         track = item['track']
#         artists = [artist['name'] for artist in track['artists']]
#         title = track['name'].split(' - ')[0]
#         remix_artist = track['name'].split(' - ')[1].replace(' Remix', '') if len(track['name'].split(' - ')) > 1 else ''

#         song_data['artists'] = artists
#         song_data['title'] = title
#         song_data['remix_artist'] = remix_artist
#         song_data['remix_type'] = 'Remix' if remix_artist else ''

#         return song_data

#     def retrieve_playlists(self, lib, opts, args):
#         no_db = opts.no_db
#         playlist_name = opts.playlist_name

#         if playlist_name:
#             playlist = self.get_playlist_by_name(playlist_name)
#             if playlist:
#                 tracks = self.sp.playlist_tracks(playlist['id'])
#                 self._log.info(f"Retrieved playlist '{playlist['name']}' with {len(tracks['items'])} songs.")
#                 print(f"Playlist: {playlist['name']} (ID: {playlist['id']})")
#                 for item in tracks['items']:
#                     song_data = self._parse_track(item)

#                     print(f" {song_data['artists']} - {song_data['title']} {song_data['remix_artist']} {song_data['remix_type']}")
#                     # Store playlist info in beets library if no_db is not set
#                     if not no_db:
#                         self.store_playlist_info(lib, playlist, track)
#             else:
#                 print(f"Playlist '{playlist_name}' not found.")
#                 self._log.info(f"Playlist '{playlist_name}' not found.")
#         else:
#             playlists = self.get_all_playlists()
#             for playlist in playlists:
#                 tracks = self.sp.playlist_tracks(playlist['id'])
#                 self._log.info(f"Retrieved playlist '{playlist['name']}' with {len(tracks['items'])} songs.")
#                 print(f"Playlist: {playlist['name']} (ID: {playlist['id']})")
#                 for item in tracks['items']:
#                     track = item['track']
#                     # print(f"  - {track['name']} by {track['artists'][0]['name']}")
#                     print(dir(track))

#                     # Store playlist info in beets library if no_db is not set
#                     if not no_db:
#                         self.store_playlist_info(lib, playlist, track)

#     def get_playlist_by_name(self, name):
#         playlists = self.get_all_playlists()
#         for playlist in playlists:
#             if playlist['name'].lower() == name.lower():
#                 return playlist
#         return None

#     def get_all_playlists(self):
#         playlists = []
#         offset = 0
#         limit = 50
#         while True:
#             results = self.sp.current_user_playlists(limit=limit, offset=offset)
#             playlists.extend(results['items'])
#             if results['next'] is None:
#                 break
#             offset += limit
#         return playlists

#     def add_to_playlist(self, lib, opts, args):
#         playlist_name_or_id = opts.playlist
#         song_dicts = eval(opts.songs)  # Use a safer parsing method in production

#         # Check if the playlist exists
#         playlists = self.get_all_playlists()
#         playlist_id = None
#         for playlist in playlists:
#             if playlist['name'] == playlist_name_or_id or playlist['id'] == playlist_name_or_id:
#                 playlist_id = playlist['id']
#                 break

#         # If the playlist doesn't exist, create it
#         if not playlist_id:
#             user_id = self.sp.current_user()['id']
#             playlist = self.sp.user_playlist_create(user_id, playlist_name_or_id)
#             playlist_id = playlist['id']

#         successful_adds = []
#         failed_adds = []
#         items_to_add = []

#         for song in song_dicts:
#             query = self.build_query(song)
#             track_id = self.search_spotify(query)
#             if track_id:
#                 successful_adds.append((song, track_id))
#                 item = Item(title=song['title'], artist=' '.join(song['artists']))
#                 items_to_add.append(item)
#             else:
#                 failed_adds.append(song['title'])

#         # Bulk insert items
#         if items_to_add:
#             lib.add(items_to_add)
#             lib.save()
#             for item, (song, track_id) in zip(items_to_add, successful_adds):
#                 item['spotify_track_id'] = track_id
#                 self.store_playlist_relation(item, playlist_id)
#                 item.store()

#         # Add found tracks to the playlist
#         if successful_adds:
#             self.sp.playlist_add_items(playlist_id, [track_id for _, track_id in successful_adds])

#         # Log the operation
#         self._log.info(f"Added {len(successful_adds)} tracks to playlist '{playlist_name_or_id}'. Failed to add: {', '.join(failed_adds) if failed_adds else 'None'}")

#         # Print summary of the operation
#         print(f"Successfully added {len(successful_adds)} tracks to playlist {playlist_name_or_id}.")
#         if failed_adds:
#             print(f"Failed to find the following tracks: {', '.join(failed_adds)}")

#     def build_query(self, song):
#         """Build a Spotify search query from song dictionary."""
#         query_parts = []
#         if 'artists' in song:
#             query_parts.append(f"artist:{' '.join(song['artists'])}")
#         if 'title' in song:
#             query_parts.append(f"track:{song['title']}")
#         if 'remix_artist' in song:
#             query_parts.append(f"remixer:{song['remix_artist']}")
#         if 'remix_type' in song:
#             query_parts.append(f"remix:{song['remix_type']}")
#         return ' '.join(query_parts)

#     def search_spotify(self, query):
#         """Search for a track on Spotify and return the best match."""
#         results = self.sp.search(q=query, type='track', limit=10)
#         tracks = results['tracks']['items']
#         best_match = None
#         best_score = 0
#         for track in tracks:
#             score = self.calculate_match_score(track, query)
#             if score > best_score:
#                 best_match = track['id']
#                 best_score = score
#         return best_match

#     def calculate_match_score(self, track, query):
#         """Calculate a match score based on query and track details."""
#         # Example scoring algorithm, to be refined based on requirements
#         score = 0
#         if query.lower() in track['name'].lower():
#             score += 1
#         if any(artist['name'].lower() in query.lower() for artist in track['artists']):
#             score += 1
#         return score

#     def store_track_info(self, lib, song, track_id, playlist_id):
#         """Store Spotify track information in the Beets library."""
#         item = lib.items(query=f"title:{song['title']} artist:{' '.join(song['artists'])}").get()
#         if item:
#             item['spotify_track_id'] = track_id
#             item.store()
#             self.store_playlist_relation(item, playlist_id)

#     def store_playlist_info(self, lib, playlist, track):
#         """Store playlist information in the Beets library."""
#         album = lib.albums(query=f"album.title:{playlist['name']}").get()  # Fully qualify the column name
#         if not album:
#             album = lib.add_album([Item(title=track['name'], artist=track['artists'][0]['name'])])
#         album['spotify_playlist_id'] = playlist['id']
#         album.store()

#     def store_playlist_relation(self, item, playlist_id):
#         """Store the relationship between a track and a playlist."""
#         if 'playlists' not in item:
#             item['playlists'] = []
#         item['playlists'].append(playlist_id)
#         item.store()

# # plugin = SpotifyCustomPlugin()
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.library import Item
import logging

class SpotifyCustomPlugin(BeetsPlugin):

    def __init__(self):
        super(SpotifyCustomPlugin, self).__init__()

        self.config.add({
            'client_id': '',
            'client_secret': '',
            'redirect_uri': 'http://localhost:8888/callback',
        })

        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=self.config['client_id'].get(),
            client_secret=self.config['client_secret'].get(),
            redirect_uri=self.config['redirect_uri'].get(),
            scope="playlist-read-private playlist-modify-private playlist-modify-public"
        ))

        self._log = logging.getLogger('beets.spotify_custom')

        # Define subcommands
        self.add_command = Subcommand('add_to_playlist', help='Add tracks to a Spotify playlist')
        self.add_command.parser.add_option('-p', '--playlist', dest='playlist', help='Playlist name or ID')
        self.add_command.parser.add_option('-s', '--songs', dest='songs', help='List of song dictionaries')
        self.add_command.func = self.add_to_playlist

        self.retrieve_command = Subcommand('retrieve_playlists', help='Retrieve all playlists and their tracks')
        self.retrieve_command.parser.add_option('--no-db', action='store_true', help='Do not add retrieved info to the database')
        self.retrieve_command.parser.add_option('-n', '--playlist-name', dest='playlist_name', help='Name of the playlist to retrieve')
        self.retrieve_command.func = self.retrieve_playlists

        self.register_listener('library_opened', self.setup)

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

    def retrieve_playlists(self, lib, opts, args):
        no_db = opts.no_db
        playlist_name = opts.playlist_name

        if playlist_name:
            playlist = self.get_playlist_by_name(playlist_name)
            if playlist:
                tracks = self.sp.playlist_tracks(playlist['spotify_id'])
                self._log.info(f"Retrieved playlist '{playlist['name']}' with {len(tracks['items'])} songs.")
                print(f"Playlist: {playlist['name']} (ID: {playlist['spotify_id']})")
                for item in tracks['items']:
                    track = item['track']
                    print(f"  - {track['name']} by {track['artists'][0]['name']}")
                    if not no_db:
                        self.store_playlist_info(lib, playlist)
                        self.store_track_info(lib, track)  # Add this line
                        internal_playlist_id = self.get_internal_playlist_id(lib, spotify_id=playlist['id'])
                        internal_track_id = self.get_internal_track_id(lib, track['id'])  # Fetch internal track ID
                        self.store_playlist_relation(lib, internal_track_id, internal_playlist_id)
            else:
                print(f"Playlist '{playlist_name}' not found.")
                self._log.info(f"Playlist '{playlist_name}' not found.")
        else:
            playlists = self.get_all_playlists()
            for playlist in playlists:
                tracks = self.sp.playlist_tracks(playlist['spotify_id'])
                self._log.info(f"Retrieved playlist '{playlist['name']}' with {len(tracks['items'])} songs.")
                print(f"Playlist: {playlist['name']} (ID: {playlist['spotify_id']})")
                for item in tracks['items']:
                    track = item['track']
                    print(f"  - {track['name']} by {track['artists'][0]['name']}")
                    if not no_db:
                        self.store_playlist_info(lib, playlist)
                        self.store_track_info(lib, track)  # Add this line
                        internal_playlist_id = self.get_internal_playlist_id(lib, spotify_id=playlist['id'])
                        internal_track_id = self.get_internal_track_id(lib, track['id'])  # Fetch internal track ID
                        self.store_playlist_relation(lib, internal_track_id, internal_playlist_id)


    def store_playlist_relation(self, lib, track_id, playlist_id):
        with lib.transaction() as tx:
            tx.query("""
            INSERT OR IGNORE INTO playlist_item (playlist_id, item_id)
            VALUES (?, ?)
            """, (playlist_id, track_id))

    def store_track_info(self, lib, track):
        print(track)
        with lib.transaction() as tx:
            tx.query("""
            INSERT OR IGNORE INTO items (title, artist, spotify_track_id)
            VALUES (?, ?, ?)
            """, (track['name'], track['artists'][0]['name'], track['id']))

            tx.query("""
            UPDATE items SET title = ?, artist = ?
            WHERE spotify_track_id = ?
            """, (track['name'], track['artists'][0]['name'], track['id']))

    def get_playlist_by_name(self, name):
        playlists = self.get_all_playlists()
        for playlist in playlists:
            if playlist['name'].lower() == name.lower():
                return playlist
        return None

    def get_all_playlists(self):
        playlists = []
        offset = 0
        limit = 50
        while True:
            results = self.sp.current_user_playlists(limit=limit, offset=offset)
            playlists.extend(results['items'])
            if results['next'] is None:
                break
            offset += limit
        return [{'name': p['name'], 'spotify_id': p['id']} for p in playlists]
    
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

    def calculate_match_score(self, track, query):
        score = 0
        if query.lower() in track['name'].lower():
            score += 1
        if any(artist['name'].lower() in query.lower() for artist in track['artists']):
            score += 1
        return score

    def store_playlist_info(self, lib, playlist):
        # Debugging: Print playlist data to inspect keys
        print("Storing playlist info:", playlist)
        # Ensure necessary keys are present
        spotify_id = playlist.get('spotify_id', None)
        if not spotify_id:
            raise ValueError("Playlist 'id' key is missing")

        with lib.transaction() as tx:
            tx.query("""
            INSERT OR IGNORE INTO playlist (name, description, spotify_id, youtube_id, path, last_edited_at, type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (playlist['name'], playlist.get('description', ''), spotify_id, '', '', '', 'playlist'))

            tx.query("""
            UPDATE playlist SET name = ?, description = ?, youtube_id = ?, path = ?, last_edited_at = ?, type = ?
            WHERE spotify_id = ?
            """, (playlist['name'], playlist.get('description', ''), '', '', '', 'playlist', spotify_id))


    def store_playlist_relation(self, lib, item_id, playlist_id):
        with lib.transaction() as tx:
            tx.query("""
            INSERT OR IGNORE INTO playlist_item (playlist_id, item_id)
            VALUES (?, ?)
            """, (playlist_id, item_id))

    def add_items_to_library(self, lib, items_to_add):
        lib.add(items_to_add)
        lib.save()
        for item in items_to_add:
            item.store()

    def _get_internal_playlist_id(self, lib, spotify_id=None, playlist_name=None):
        with lib.transaction() as tx:
            if spotify_id:
                result = tx.query("SELECT id FROM playlist WHERE spotify_id = ?", (spotify_id,))
            elif playlist_name:
                result = tx.query("SELECT id FROM playlist WHERE name = ?", (playlist_name,))
            else:
                return None
            row = result.fetchone()
            return row['id'] if row else None
        
    def get_internal_track_id(self, lib, spotify_id):
        with lib.transaction() as tx:
            result = tx.query("SELECT id FROM items WHERE spotify_track_id = ?", (spotify_id,))
            row = result.fetchone()
            return row['id'] if row else None

    def get_internal_playlist_id(self, lib, spotify_id=None, playlist_name=None):
        with lib.transaction() as tx:
            if spotify_id:
                result = tx.query("SELECT id FROM playlist WHERE spotify_id = ?", (spotify_id,))
            elif playlist_name:
                result = tx.query("SELECT id FROM playlist WHERE name = ?", (playlist_name,))
            else:
                return None
            row = result.fetchone()
            return row['id'] if row else None
