# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function

import re
import json
import base64
import webbrowser

import requests

from beets import ui
from beets.plugins import BeetsPlugin
from beets.util import confit
from beets.autotag.hooks import AlbumInfo, TrackInfo


class SpotifyPlugin(BeetsPlugin):
    # URL for the Web API of Spotify
    # Documentation here: https://developer.spotify.com/web-api/search-item/
    oauth_token_url = 'https://accounts.spotify.com/api/token'
    base_url = 'https://api.spotify.com/v1/search'
    open_url = 'http://open.spotify.com/track/'
    album_url = 'https://api.spotify.com/v1/albums/'
    track_url = 'https://api.spotify.com/v1/tracks/'
    playlist_partial = 'spotify:trackset:Playlist:'
    id_regex = r'(^|open\.spotify\.com/{}/)([0-9A-Za-z]{{22}})'

    def __init__(self):
        super(SpotifyPlugin, self).__init__()
        self.config.add(
            {
                'mode': 'list',
                'tiebreak': 'popularity',
                'show_failures': False,
                'artist_field': 'albumartist',
                'album_field': 'album',
                'track_field': 'title',
                'region_filter': None,
                'regex': [],
                'client_id': 'N3dliiOOTBEEFqCH5NDDUmF5Eo8bl7AN',
                'client_secret': '6DRS7k66h4643yQEbepPxOuxeVW0yZpk',
                'tokenfile': 'spotify_token.json',
                'source_weight': 0.5,
                'user_token': '',
            }
        )
        self.config['client_secret'].redact = True

        """Path to the JSON file for storing the OAuth access token."""
        self.tokenfile = self.config['tokenfile'].get(
            confit.Filename(in_app_dir=True)
        )
        # self.register_listener('import_begin', self.setup)

    def setup(self):
        """Retrieve previously saved OAuth token or generate a new one"""
        try:
            with open(self.tokenfile) as f:
                token_data = json.load(f)
        except IOError:
            self.authenticate()
        else:
            self.access_token = token_data['access_token']

    def authenticate(self):
        headers = {
            'Authorization': 'Basic {}'.format(
                base64.b64encode(
                    '{}:{}'.format(
                        self.config['client_id'].as_str(),
                        self.config['client_secret'].as_str(),
                    )
                )
            )
        }
        response = requests.post(
            self.oauth_token_url,
            data={'grant_type': 'client_credentials'},
            headers=headers,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise ui.UserError(
                u'Spotify authorization failed: {}\n{}'.format(
                    e, response.content
                )
            )
        self.access_token = response.json()['access_token']

        # Save the token for later use.
        self._log.debug(u'Spotify access token: {}', self.access_token)
        with open(self.tokenfile, 'w') as f:
            json.dump({'access_token': self.access_token}, f)

    @property
    def auth_header(self):
        if not hasattr(self, 'access_token'):
            self.setup()
        return {'Authorization': 'Bearer {}'.format(self.access_token)}

    def _handle_response(self, request_type, url, params=None):
        response = request_type(url, headers=self.auth_header, params=params)
        if response.status_code != 200:
            if u'token expired' in response.text:
                self._log.debug(
                    'Spotify access token has expired. Reauthenticating.'
                )
                self.authenticate()
                self._handle_response(request_type, url, params=params)
            else:
                raise ui.UserError(u'Spotify API error:\n{}', response.text)
        return response

    def album_for_id(self, album_id):
        """
        Fetches an album by its Spotify album ID or URL and returns an AlbumInfo object
        or None if the album is not found.
        """
        self._log.debug(u'Searching for album {}', album_id)
        match = re.search(self.id_regex.format('album'), album_id)
        if not match:
            return None
        spotify_album_id = match.group(2)

        response = self._handle_response(
            requests.get, self.album_url + spotify_album_id
        )

        data = response.json()

        artist, artist_id = self._get_artist(data['artists'])

        date_parts = [int(part) for part in data['release_date'].split('-')]

        if data['release_date_precision'] == 'day':
            year, month, day = date_parts
        elif data['release_date_precision'] == 'month':
            year, month = date_parts
            day = None
        elif data['release_date_precision'] == 'year':
            year = date_parts
            month = None
            day = None

        album = AlbumInfo(
            album=data['name'],
            album_id=album_id,
            artist=artist,
            artist_id=artist_id,
            tracks=None,
            asin=None,
            albumtype=data['album_type'],
            va=False,
            year=year,
            month=month,
            day=day,
            label=None,
            mediums=None,
            artist_sort=None,
            releasegroup_id=None,
            catalognum=None,
            script=None,
            language=None,
            country=None,
            albumstatus=None,
            media=None,
            albumdisambig=None,
            releasegroupdisambig=None,
            artist_credit=None,
            original_year=None,
            original_month=None,
            original_day=None,
            data_source='Spotify',
            data_url=None,
        )

        return album

    def track_for_id(self, track_id):
        """
        Fetches a track by its Spotify track ID or URL and returns a TrackInfo object
        or None if the track is not found.
        """
        self._log.debug(u'Searching for track {}', track_id)
        match = re.search(self.id_regex.format('track'), track_id)
        if not match:
            return None
        spotify_track_id = match.group(2)

        response = self._handle_response(
            requests.get, self.track_url + spotify_track_id
        )
        data = response.json()
        artist, artist_id = self._get_artist(data['artists'])
        track = TrackInfo(
            title=data['title'],
            track_id=spotify_track_id,
            release_track_id=data.get('album').get('id'),
            artist=artist,
            artist_id=artist_id,
            length=data['duration_ms'] / 1000,
            index=None,
            medium=None,
            medium_index=data['track_number'],
            medium_total=None,
            artist_sort=None,
            disctitle=None,
            artist_credit=None,
            data_source=None,
            data_url=None,
            media=None,
            lyricist=None,
            composer=None,
            composer_sort=None,
            arranger=None,
            track_alt=None,
        )
        return track

    def _get_artist(self, artists):
        """
        Returns an artist string (all artists) and an artist_id (the main
        artist) for a list of Beatport release or track artists.
        """
        artist_id = None
        artist_names = []
        for artist in artists:
            if not artist_id:
                artist_id = artist['id']
            name = artist['name']
            # Strip disambiguation number.
            name = re.sub(r' \(\d+\)$', '', name)
            # Move articles to the front.
            name = re.sub(r'^(.*?), (a|an|the)$', r'\2 \1', name, flags=re.I)
            artist_names.append(name)
        artist = ', '.join(artist_names).replace(' ,', ',') or None
        return artist, artist_id

    def commands(self):
        def queries(lib, opts, args):
            success = self.parse_opts(opts)
            if success:
                results = self.query_spotify(lib, ui.decargs(args))
                self.output_results(results)

        spotify_cmd = ui.Subcommand(
            'spotify', help=u'build a Spotify playlist'
        )
        spotify_cmd.parser.add_option(
            u'-m',
            u'--mode',
            action='store',
            help=u'"open" to open Spotify with playlist, '
            u'"list" to print (default)',
        )
        spotify_cmd.parser.add_option(
            u'-f',
            u'--show-failures',
            action='store_true',
            dest='show_failures',
            help=u'list tracks that did not match a Spotify ID',
        )
        spotify_cmd.func = queries
        return [spotify_cmd]

    def parse_opts(self, opts):
        if opts.mode:
            self.config['mode'].set(opts.mode)

        if opts.show_failures:
            self.config['show_failures'].set(True)

        if self.config['mode'].get() not in ['list', 'open']:
            self._log.warning(
                u'{0} is not a valid mode', self.config['mode'].get()
            )
            return False

        self.opts = opts
        return True

    def query_spotify(self, lib, query):
        results = []
        failures = []

        items = lib.items(query)

        if not items:
            self._log.debug(
                u'Your beets query returned no items, ' u'skipping spotify'
            )
            return

        self._log.info(u'Processing {0} tracks...', len(items))

        for item in items:

            # Apply regex transformations if provided
            for regex in self.config['regex'].get():
                if (
                    not regex['field']
                    or not regex['search']
                    or not regex['replace']
                ):
                    continue

                value = item[regex['field']]
                item[regex['field']] = re.sub(
                    regex['search'], regex['replace'], value
                )

            # Custom values can be passed in the config (just in case)
            artist = item[self.config['artist_field'].get()]
            album = item[self.config['album_field'].get()]
            query = item[self.config['track_field'].get()]
            search_url = query + " album:" + album + " artist:" + artist

            # Query the Web API for each track, look for the items' JSON data
            r = self._handle_response(
                requests.get,
                self.base_url,
                params={"q": search_url, "type": "track"},
            )
            self._log.debug('{}', r.url)
            try:
                r.raise_for_status()
            except requests.exceptions.HTTPError as e:
                self._log.debug(
                    u'URL returned a {0} error', e.response.status_code
                )
                failures.append(search_url)
                continue

            r_data = r.json()['tracks']['items']

            # Apply market filter if requested
            region_filter = self.config['region_filter'].get()
            if region_filter:
                r_data = [
                    x
                    for x in r_data
                    if region_filter in x['available_markets']
                ]

            # Simplest, take the first result
            chosen_result = None
            if len(r_data) == 1 or self.config['tiebreak'].get() == "first":
                self._log.debug(
                    u'Spotify track(s) found, count: {0}', len(r_data)
                )
                chosen_result = r_data[0]
            elif len(r_data) > 1:
                # Use the popularity filter
                self._log.debug(
                    u'Most popular track chosen, count: {0}', len(r_data)
                )
                chosen_result = max(r_data, key=lambda x: x['popularity'])

            if chosen_result:
                results.append(chosen_result)
            else:
                self._log.debug(u'No spotify track found: {0}', search_url)
                failures.append(search_url)

        failure_count = len(failures)
        if failure_count > 0:
            if self.config['show_failures'].get():
                self._log.info(
                    u'{0} track(s) did not match a Spotify ID:', failure_count
                )
                for track in failures:
                    self._log.info(u'track: {0}', track)
                self._log.info(u'')
            else:
                self._log.warning(
                    u'{0} track(s) did not match a Spotify ID;\n'
                    u'use --show-failures to display',
                    failure_count,
                )

        return results

    def output_results(self, results):
        if results:
            ids = [x['id'] for x in results]
            if self.config['mode'].get() == "open":
                self._log.info(u'Attempting to open Spotify with playlist')
                spotify_url = self.playlist_partial + ",".join(ids)
                webbrowser.open(spotify_url)

            else:
                for item in ids:
                    print(self.open_url + item)
        else:
            self._log.warning(u'No Spotify tracks found from beets query')
