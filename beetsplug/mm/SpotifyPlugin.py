# SF
import spotipy
from spotipy.oauth2 import SpotifyOAuth
# Beets
from beets.plugins import BeetsPlugin
from beets import config

# Varia
import logging
from typing import List, Dict
import re
import requests

from contextlib import contextmanager

@contextmanager
def spotify_plugin():
    plugin = SpotifyPlugin()
    try:
        yield plugin
    finally:
        plugin.cleanup()

class SpotifyPlugin(BeetsPlugin):

    def __init__(self):
        super().__init__()

        self.session = requests.Session()
        
        self.api = self.initialize_api()
        self._log = logging.getLogger('beets.SpotifyPlugin')

        self.pl_to_skip = str(config['mm']['SpotifyPlugin']['pl_to_skip']).split(',')
        self.valid_pl_prefix = str(config['mm']['SpotifyPlugin']['valid_pl_prefix'])

    def initialize_api(self):
        return spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id = config['mm']['SpotifyPlugin']['client_id'].get(),
            client_secret = config['mm']['SpotifyPlugin']['client_secret'].get(),
            redirect_uri = config['mm']['SpotifyPlugin']['redirect_uri'].get(),
            scope="playlist-read-private playlist-modify-private playlist-modify-public",
            requests_session = self.session
        ))
    
    def cleanup(self):
        """Explicitly close the requests session."""
        try:
            if self.session:
                self.session.close()  # Close the session to clean up resources
                self._log.info("Spotify session closed.")
        except Exception as e:
            self._log.error(f"Error during cleanup: {e}")

        try:
            self.api = None
            self._log.info("Spotify API client dereferenced.")
        except Exception as e:
            self._log.error(f"Error during Spotify API cleanup: {e}")

    def retrieve_info(self, lib, playlist_name=None, playlist_type=None, no_db=None):

        items = list()

        # PLYALISTS TO PROCESS
        # all
        all_playlists = self._get_all_playlists()
        # filter mm playlists 
        playlists_to_process = [playlist for playlist in all_playlists if playlist['playlist_name'][:2] == self.valid_pl_prefix]
        # filter ignore
        playlists_to_process = [playlist for playlist in playlists_to_process if playlist['playlist_name'] not in self.pl_to_skip]                
        # filter type
        playlists_to_process = [playlist for playlist in playlists_to_process if playlist_type in playlist['playlist_name']] if playlist_type else playlists_to_process
        # filter name
        playlists_to_process = [playlist for playlist in playlists_to_process if playlist_name.lower() in playlist['playlist_name'].lower()] if playlist_name else playlists_to_process
        
        print("PROCESSING")
        for pl in playlists_to_process:
            print(pl['playlist_name'])

        for playlist in playlists_to_process:
            # get playlist from spotify API
            playlist_name = playlist['playlist_name']
            # process playlist if it exists
            if playlist:
                # get all tracks
                tracks = self.api.playlist_tracks(playlist['spotify_id'])
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
                        item = self._store_item(lib, song_data, update_genre=True)
                        items.append(item)
                        # UPSERT PLAYLIST
                        playlist_id = self._store_playlist(lib, playlist)
                        # PLAYLIST_ITEM  RELATION
                        self._store_playlist_relation(lib, item.id, playlist_id)
            else:
                print(f"Playlist '{playlist_name}' not found.")
                self._log.info(f"Playlist '{playlist_name}' not found.")

        return items

    def _get_all_playlists(self) -> List[Dict[str, str]]:
        playlists = []
        offset = 0
        limit = 50
        while True:
            results = self.api.current_user_playlists(limit=limit, offset=offset)
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
    
