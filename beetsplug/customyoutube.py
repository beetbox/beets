# customyoutube.py
from beets.plugins import BeetsPlugin

import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import logging
import google_auth_oauthlib
import googleapiclient.discovery
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from json.decoder import JSONDecodeError
import json
from beets.ui import Subcommand
from typing import List, Dict, Union
import datetime
from beets.library import Item


from beets.plugins import BeetsPlugin
import beetsplug.ssp as ssp

class YouTubePlugin(BeetsPlugin):
    # PLUGIN BOILERPLATE
    def __init__(self):
        super().__init__()
        self.config.add({
            'secrets_file': 'yt_client_secret.json',
            'youtube_field': 'youtube_info',
            'scopes': 'https://www.googleapis.com/auth/youtube',
            'api_name': 'youtube',
            'api_version': 'v3',
            'pl_to_skip': ''
        })

        self.authenticate()

        # init api
        self.yt = self.initialize_youtube_api(self.config['secrets_file'].get())
        # init SSP
        self.titleparser = ssp.SongStringParser()

        # logger
        self._log = logging.getLogger('beets.spotify_custom')

        # commands
        self.retrieve_command = Subcommand('retrieve_yt', help='get playlist(s) from youtube')
        self.retrieve_command.parser.add_option('--type', dest='playlist_type', choices=['pl', 'mm'], default='mm', help="process 'pl' playlists or regular genre/subgenre playlists")
        self.retrieve_command.parser.add_option('--no-db', action='store_true', help='Do not add retrieved info to the database')
        self.retrieve_command.parser.add_option('--n', dest='playlist_name', help='Name of the playlist to retrieve')
        self.retrieve_command.func = self.retrieve_info

        self.register_listener('library_opened', self.setup)

    def commands(self):
        return [self.retrieve_command]

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
    
    # AUTHENTICATION
    
    def authenticate(self):  
        # create directory to save credentials if it does not exits    
        auth_path = os.path.join(os.curdir, 'auth')

        if not os.path.isdir(auth_path):
            os.mkdir(auth_path)
        # OAUTH
        credentials = None
        # check if stored credentials are still valid
        try:
            credentials = Credentials.from_authorized_user_file(auth_path + '/yt_credentials.json', [str(self.config['scopes'])])
            credentials.refresh(Request())
        # crete new credentials if old expired
        except (RefreshError, JSONDecodeError) as error:
            credentials = None
            secrets_file = os.path.join(os.curdir, 'auth\\' + str(self.config['secrets_file']))
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(secrets_file, [str(self.config['scopes'])])
            credentials = flow.run_local_server()

            cred_file = {"token": credentials.token,
                         "refresh_token": credentials.refresh_token,
                         "token_uri": credentials.token_uri,
                         "client_id": credentials.client_id,
                         "client_secret": credentials.client_secret,
                         "scopes": credentials.scopes}

            # sand store them in json
            with open(auth_path + '/yt_credentials.json', 'w') as token:
                token.write(json.dumps(cred_file))
                print()
        
        self.credentials = credentials
        return 

    def initialize_youtube_api(self, client_secrets_file):
        
        api_name = self.config['api_name']
        api_version = self.config['api_version']

        api_object = googleapiclient.discovery.build(api_name, api_version, credentials=self.credentials)
        return api_object

    # PLAYLISTS GET 
    
    def retrieve_info(self, lib, opts, args):
        """ Check playlists on platforms for new songs and/or update their genres / playlists. 

            1. get all playlists to process (based on playlist_name & playlist_type)
            2. get all tracks in a playlist 
            3. parse track to extract song_data from it
                3.5 YOUTUBE: check if video title already exist. If not: get song data using ChatGPT assistant
            4. 

        Args:
            lib (_type_): _description_
            opts (_type_): _description_
            args (_type_): _description_
        """
        # CLI arguments
        no_db = opts.no_db
        playlist_name = opts.playlist_name
        playlist_type = opts.playlist_type

        # PLYALISTS TO PROCESS
        # all
        all_playlists = self._get_all_playlists()
        # filter mm playlists 
        playlists_to_process = [playlist for playlist in all_playlists if playlist['playlist_name'][:2] == str(self.config['valid_pl_prefix'])]
        # filter ignore
        playlists_to_process = [playlist for playlist in playlists_to_process if playlist['playlist_name'] not in str(self.config['pl_to_skip']).split(",")]                
        # filter type
        playlists_to_process = [playlist for playlist in playlists_to_process if playlist_type in playlist['playlist_name']] if playlist_type else playlists_to_process
        # filter name
        playlists_to_process = [playlist for playlist in playlists_to_process if playlist_name.lower() in playlist['playlist_name'].lower()] if playlist_name else playlists_to_process
        
        print("PROCESSING")
        for pl in playlists_to_process:
            print(pl['playlist_name'])


        for playlist in playlists_to_process:
            playlist_name = playlist['playlist_name']
            if playlist:
                # get all tracks
                tracks = self._get_videos_from_playlist(playlist['playlist_id'], playlist_name)
                self._log.info(f"Retrieved playlist '{playlist['playlist_name']}' with {len(tracks)} songs.")             
                for item in tracks:
                    # check if already in db based on title   
                    title = item['title']             
                    self._log.info(f"Processing track with title: {title}")
                    title_escaped = title.replace("'", "\\'").replace('"', '\\"')
                    title_exists = lib.items(f"youtube_title:{title_escaped}").get()

                    # skip existing items
                    if title_exists:
                        continue

                    # extract info
                    song_data = self._parse_track_item(lib, opts, item, playlist, playlist_type)


                    print(title)
                    for k, v in song_data.items():
                        print(f'{k}\t\t{v}')

                    print()


                    quit()

        return
    
    def _get_all_playlists(self) -> List[Dict[str, Union[str, int, float]]]:
        playlists = []
        request = self.yt.playlists().list(
            part='id,snippet',
            mine=True,
            maxResults=50
        )

        while request:
            try:
                response = request.execute()
                playlists.extend(response['items'])
                request = self.yt.playlists().list_next(request, response)
            except HttpError as e:
                print(f"An HTTP error {e.resp.status} occurred: {e.content}")
                break
        
        playlists = [{'playlist_id': playlist['id'],
                      'playlist_name': playlist['snippet']['title'],
                      'playlist_description': playlist['snippet']['description']} for playlist in playlists]

        return playlists

    def _get_videos_from_playlist(self, playlist_id: str, playlist_name: str='') -> List[Dict[str, Union[str, int, float]]]:
        videos = []
        request = self.yt.playlistItems().list(
            part='contentDetails,snippet',
            playlistId=playlist_id,
            maxResults=50
        )

        while request:
            try:
                response = request.execute()
                videos.extend(response['items'])
                request = self.yt.playlistItems().list_next(request, response)
            except HttpError as e:
                print(f"An HTTP error {e.resp.status} occurred: {e.content}")
                break
        
        tracks = []
        for video in videos:
            track_info = {'youtube_id': video['id'],
                    'title': video['snippet']['title'],
                    'description': video['snippet']['description'],
                    'video_id': video['contentDetails']['videoId']}
            
            try:
                track_info['channel'] = video['snippet']['videoOwnerChannelTitle']
            except KeyError:
                self._log.warning(f"{video['snippet']['title']} in playlist: {playlist_name}")
                continue

            tracks.append(track_info)
        return tracks

    def _parse_track_item(self, lib, opts, item, playlist, playlist_type) -> Dict:
        song_data = dict()

        # get title
        title = item['title']
        # fix title if artist is hidden in the topic 
        if ' - Topic' in item['channel']:
            a = item['channel'].split('- Topic')[0].strip()
            title = a + ' - ' + title
        # parse using CHAPPIE AGENT
        title, song_data = self.titleparser.send_gpt_request(lib, opts, args=[title])[0]

        # GENRE / SUBGENRE
        if playlist_type != 'pl':
            playlist_split = playlist['playlist_name'].split(' - ')
            if len(playlist_split) > 2:
                _, genre, subgenre = playlist_split
            else:
                _, genre = playlist_split

        # populate dict 
        song_data['youtube_id'] = item['youtube_id']
        song_data['video_id'] = item['video_id']
        song_data['playlist_name'] = playlist['playlist_name']
        song_data['playlist_id'] = playlist['playlist_id']

        # ARTISTS
        artists = song_data.pop('artists')
        if song_data['feat_artist']:
            artists += [song_data['feat_artist']]
        if song_data['remix_artist']:
            artists += song_data['remix_artist']
        # remove duplicates and substrings
        substrings = {a for a in artists for other in artists if a != other and a in other}
        artists = [a for a in artists if a not in substrings]
        # sort
        artists = sorted(artists)
        song_data['artists'] = artists
        return


    # DATABASE

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
    
 