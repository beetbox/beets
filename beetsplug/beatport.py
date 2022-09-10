# This file is part of beets.
# Copyright 2016, Adrian Sampson.
# Copyright 2022, Szymon "Samik" Tarasiński.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Adds Beatport release and track search support to the autotagger
"""

import json
import re
import time
from datetime import timedelta, datetime
from json import JSONDecodeError
from urllib.parse import urlencode

from beets.library import MusicalKey

import beets
import beets.ui
import requests
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.plugins import BeetsPlugin, MetadataSourcePlugin, get_distance
import confuse

USER_AGENT = f'beets/{beets.__version__} +https://beets.io/'


class BeatportAPIError(Exception):
    pass


class BeatportOAuthToken:
    def __init__(self, data):
        self.access_token = str(data['access_token'])
        if 'expires_at' in data:
            self.expires_at = data['expires_at']
        else:
            self.expires_at = time.time() + int(data['expires_in'])
        self.refresh_token = str(data['refresh_token'])

    def is_expired(self):
        """ Checks if token is expired
        """
        return time.time() + 30 >= self.expires_at

    def encode(self):
        """ Encodes the class into json serializable object
        """
        return {
            'access_token': self.access_token,
            'expires_at': self.expires_at,
            'refresh_token': self.refresh_token
        }


class BeatportLabel:
    def __init__(self, data):
        self.id = str(data['id'])
        self.name = str(data['name'])

    def __str__(self):
        return "<BeatportLabel: {}>".format(self.name)

    def __repr__(self):
        return str(self)


class BeatportArtist:
    def __init__(self, data):
        self.id = str(data['id'])
        self.name = str(data['name'])

    def __str__(self):
        return "<BeatportArtist: {}>".format(self.name)

    def __repr__(self):
        return str(self)


class BeatportRelease:
    def __init__(self, data):
        self.id = str(data['id'])
        self.name = str(data['name'])
        self.artists = []
        self.tracks = []
        self.type = None
        if 'artists' in data:
            self.artists = [BeatportArtist(x) for x in data['artists']]
        if 'label' in data:
            self.label = BeatportLabel(data['label'])
        if 'catalog_number' in data:
            self.catalog_number = str(data['catalog_number'])
        if 'slug' in data:
            self.url = "https://beatport.com/release/{}/{}" \
                .format(data['slug'], data['id'])
        if 'type' in data:
            self.type = data['type']['name']
        if 'publish_date' in data:
            self.publish_date = datetime.strptime(
                data['publish_date'], '%Y-%m-%d')

    def __str__(self):
        if len(self.artists) < 4:
            artist_str = ", ".join(x.name for x in self.artists)
        else:
            artist_str = "Various Artists"
        return "<BeatportRelease: {} - {} ({})>" \
            .format(artist_str, self.name, self.catalog_number)

    def __repr__(self):
        return str(self)


class BeatportTrack:
    def __init__(self, data):
        self.id = str(data['id'])
        self.name = str(data['name'])
        self.artists = [BeatportArtist(x) for x in data['artists']]
        self.length = timedelta(milliseconds=data.get('length_ms', 0) or 0)
        self.number = None
        self.initial_key = None
        self.url = None
        self.bpm = None
        self.genre = None
        if not self.length:
            try:
                min, sec = data.get('length', '0:0').split(':')
                self.length = timedelta(minutes=int(min), seconds=int(sec))
            except ValueError:
                pass
        if data.get('key') and data['key']['name']:
            self.initial_key = self._normalize_key(str(data['key']['name']))
        if data.get('bpm'):
            self.bpm = int(data['bpm'])
        if 'sub_genre' in data and data['sub_genre']:
            self.genre = str(data['sub_genre']['name'])
        elif 'genre' in data and data['genre']:
            self.genre = str(data['genre']['name'])
        if 'mix_name' in data:
            self.mix_name = data['mix_name']
        if 'number' in data:
            self.number = data['number']
        if 'release' in data:
            self.release = BeatportRelease(data['release'])
        if 'remixers' in data:
            self.remixers = data['remixers']
        if 'slug' in data:
            self.url = "https://beatport.com/track/{}/{}" \
                .format(data['slug'], data['id'])

    def __str__(self):
        artist_str = ", ".join(x.name for x in self.artists)
        return "<BeatportTrack: {} - {} ({})>" \
            .format(artist_str, self.name, self.mix_name)

    def __repr__(self):
        return str(self)

    def _normalize_key(self, key):
        """ Normalize new Beatport key name format (e.g "Eb Major, C# Minor)
         for backwards compatibility

        :param key:    Key name
        """
        (letter_sign, chord) = key.split(" ")
        return MusicalKey().normalize((letter_sign + chord.lower())[:-2])


class BeatportMyAccount:
    def __init__(self, data):
        self.id = str(data['id'])
        self.email = str(data['email'])
        self.username = str(data['username'])

    def __str__(self):
        return "<BeatportMyAccount: {} <{}>>" \
            .format(self.username, self.email)

    def __repr__(self):
        return str(self)


class Beatport4Client:
    def __init__(self, log, beatport_token=None):
        """ Initiate the client and make sure it is correctly authorized
        If beatport_token is passed, it is used to make a call to
        /my/account endpoint to check if the token is access_token is valid

        :param beatport_token:    BeatportOAuthToken
        """
        self._api_base = 'https://api.beatport.com/v4'
        self._beatport_client_id = '0GIvkCltVIuPkkwSJHp6NDb3s0potTjLBQr388Dd'
        self._beatport_redirect_uri = '{}/auth/o/post-message/' \
            .format(self._api_base)
        self.beatport_token = beatport_token
        self._log = log

        # Token from the file passed
        if self.beatport_token and not self.beatport_token.is_expired():
            self._log.debug('Trying beatport token loaded from file')
            try:
                my_account = self.get_my_account()
                self._log.debug(
                    'Beatport authorized with stored token as {0} <{1}>',
                    my_account.username, my_account.email)
            except BeatportAPIError as e:
                # Token from the file could be invalid, authorize and fetch new
                self._log.debug('Beatport token loaded from file invalid')

                # TODO: uncomment when authorizing is possible
                # self.beatport_token = self._authorize()
                raise e
        else:
            raise BeatportAPIError('Token missing or expired')

    def _authorize(self):
        """ Authorize client and fetch access token.

        :returns:               Beatport OAuth token
        :rtype:                 :py:class:`BeatportOAuthToken`
        """
        # TODO: implement  when Beatport opens public authorization
        pass

    def get_my_account(self):
        """ Get information about current account.

        :returns:               The user account information
        :rtype:                 :py:class:`BeatportMyAccount`
        """
        response = self._get('/my/account')
        return BeatportMyAccount(response)

    def search(self, query, model='releases', details=True):
        """ Perform a search of the Beatport catalogue.

        :param query:           Query string
        :param model:           Type of releases to search for, can be
                                'release' or 'track'
        :param details:         Retrieve additional information about the
                                search results. Currently this will fetch
                                the tracklist for releases and do nothing for
                                tracks
        :returns:               Search results
        :rtype:                 generator that yields
                                py:class:`BeatportRelease` or
                                :py:class:`BeatportTrack`
        """
        response = self._get('catalog/search', q=query, per_page=5, type=model)
        if model == 'releases':
            for release in response['releases']:
                if details:
                    release = self.get_release(release['id'])
                    if release:
                        yield release
                    continue
                yield BeatportRelease(release)
        elif model == 'tracks':
            for track in response['tracks']:
                yield BeatportTrack(track)

    def get_release(self, beatport_id):
        """ Get information about a single release.

        :param beatport_id:     Beatport ID of the release
        :returns:               The matching release
        :rtype:                 :py:class:`BeatportRelease`
        """
        try:
            response = self._get(f'/catalog/releases/{beatport_id}/')
        except BeatportAPIError as e:
            self._log.debug((str(e)))
            return None
        if response:
            release = BeatportRelease(response)
            release.tracks = self.get_release_tracks(beatport_id)
            return release
        return None

    def get_release_tracks(self, beatport_id):
        """ Get all tracks for a given release.

        :param beatport_id:     Beatport ID of the release
        :returns:               Tracks in the matching release
        :rtype:                 list of :py:class:`BeatportTrack`
        """
        try:
            response = self._get(f'/catalog/releases/{beatport_id}/tracks/',
                                 perPage=100)
        except BeatportAPIError as e:
            self._log.debug((str(e)))
            return []
        # we are not using BeatportTrack(t) because "number" field is missing
        return [self.get_track(t['id']) for t in response]

    def get_track(self, beatport_id):
        """ Get information about a single track.

        :param beatport_id:     Beatport ID of the track
        :returns:               The matching track
        :rtype:                 :py:class:`BeatportTrack`
        """
        try:
            response = self._get(f'/catalog/tracks/{beatport_id}/')
        except BeatportAPIError as e:
            self._log.debug(str(e))
            return None
        return BeatportTrack(response)

    def _make_url(self, endpoint, query=None):
        """ Get complete URL for a given API endpoint. """
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        if query:
            return self._api_base + endpoint + '?' + urlencode(query)
        return self._api_base + endpoint

    def _get(self, endpoint, **kwargs):
        """ Perform a GET request on a given API endpoint.

        Automatically extracts result data from the response and converts HTTP
        exceptions into :py:class:`BeatportAPIError` objects.
        """
        try:
            headers = {
                'Authorization': 'Bearer {}'
                .format(self.beatport_token.access_token),
                'User-Agent': USER_AGENT
            }
            response = requests.get(self._make_url(endpoint),
                                    params=kwargs,
                                    headers=headers)
        except Exception as e:
            raise BeatportAPIError(
                "Error connecting to Beatport API: {}"
                .format(e)
            )
        if not response:
            raise BeatportAPIError(
                "Error {0.status_code} for '{0.request.path_url}"
                .format(response)
            )

        json_response = response.json()

        # Handle both list and single entity responses
        if 'results' in json_response:
            return json_response['results']
        return json_response


class Beatport4Plugin(BeetsPlugin):
    data_source = 'Beatport'

    def __init__(self):
        super().__init__()
        self.config.add({
            'tokenfile': 'beatport_token.json',
            'source_weight': 0.5,
        })
        self.client = None
        self.register_listener('import_begin', self.setup)

    def setup(self):
        """Loads access token from the file, initializes the client
        and writes the token to the file if new one is fetched during
        client authorization
        """
        beatport_token = None
        # Get the OAuth token from a file
        try:
            with open(self._tokenfile()) as f:
                beatport_token = BeatportOAuthToken(json.load(f))

        except (OSError, AttributeError, JSONDecodeError):
            # File does not exist, or has invalid format
            pass

        try:
            self.client = Beatport4Client(
                log=self._log,
                beatport_token=beatport_token
            )
        except BeatportAPIError as e:
            # Invalid token
            beets.ui.print_(str(e))

            # Retry manually
            token = self._prompt_for_token()

            self.client = Beatport4Client(
                log=self._log,
                beatport_token=token
            )

        with open(self._tokenfile(), 'w') as f:
            json.dump(self.client.beatport_token.encode(), f)

    def _prompt_for_token(self):
        """Prompts user to paste the OAuth token in the console and
        writes the contents to the beatport_token.json file.
        Returns parsed JSON.
        """
        data = json.loads(beets.ui.input_("Paste the Beatport OAuth access "
                                          "token:"))

        return BeatportOAuthToken(data)

    def _tokenfile(self):
        """Get the path to the JSON file for storing the OAuth token.
        """
        return self.config['tokenfile'].get(confuse.Filename(in_app_dir=True))

    def album_distance(self, items, album_info, mapping):
        """Returns the Beatport source weight and the maximum source weight
        for albums.
        """
        return get_distance(
            data_source=self.data_source,
            info=album_info,
            config=self.config
        )

    def track_distance(self, item, track_info):
        """Returns the Beatport source weight and the maximum source weight
        for individual tracks.
        """
        return get_distance(
            data_source=self.data_source,
            info=track_info,
            config=self.config
        )

    def candidates(self, items, artist, release, va_likely, extra_tags=None):
        """Returns a list of AlbumInfo objects for beatport search results
        matching release and artist (if not various).
        """
        if va_likely:
            query = release
        else:
            query = f'{artist} {release}'
        try:
            return self._get_releases(query)
        except BeatportAPIError as e:
            self._log.debug('API Error: {0} (query: {1})', e, query)
            return []

    def item_candidates(self, item, artist, title):
        """Returns a list of TrackInfo objects for beatport search results
        matching title and artist.
        """
        query = f'{artist} {title}'
        try:
            return self._get_tracks(query)
        except BeatportAPIError as e:
            self._log.debug('API Error: {0} (query: {1})', e, query)
            return []

    def album_for_id(self, release_id):
        """Fetches a release by its Beatport ID and returns an AlbumInfo object
        or None if the query is not a valid ID or release is not found.
        """
        self._log.debug('Searching for release {0}', release_id)
        match = re.search(r'(^|beatport\.com/release/.+/)(\d+)$', release_id)
        if not match:
            self._log.debug('Not a valid Beatport release ID.')
            return None
        release = self.client.get_release(match.group(2))
        if release:
            return self._get_album_info(release)
        return None

    def track_for_id(self, track_id):
        """Fetches a track by its Beatport ID and returns a
        TrackInfo object or None if the track is not a valid
        Beatport ID or track is not found.
        """
        self._log.debug('Searching for track {0}', track_id)
        match = re.search(r'(^|beatport\.com/track/.+/)(\d+)$', track_id)
        if not match:
            self._log.debug('Not a valid Beatport track ID.')
            return None
        bp_track = self.client.get_track(match.group(2))
        if bp_track is not None:
            return self._get_track_info(bp_track)
        return None

    def _get_releases(self, query):
        """Returns a list of AlbumInfo objects for a beatport search query.
        """
        # Strip non-word characters from query. Things like "!" and "-" can
        # cause a query to return no results, even if they match the artist or
        # album title. Use `re.UNICODE` flag to avoid stripping non-english
        # word characters.
        query = re.sub(r'\W+', ' ', query, flags=re.UNICODE)
        # Strip medium information from query, Things like "CD1" and "disk 1"
        # can also negate an otherwise positive result.
        query = re.sub(r'\b(CD|disc)\s*\d+', '', query, flags=re.I)
        albums = [self._get_album_info(x)
                  for x in self.client.search(query)]
        return albums

    def _get_album_info(self, release):
        """Returns an AlbumInfo object for a Beatport Release object.
        """
        va = len(release.artists) > 3
        artist, artist_id = self._get_artist(
            ((artist.id, artist.name) for artist in release.artists)
        )
        if va:
            artist = "Various Artists"
        tracks = [self._get_track_info(x) for x in release.tracks]

        return AlbumInfo(album=release.name, album_id=release.id,
                         artist=artist, artist_id=artist_id, tracks=tracks,
                         albumtype=release.type, va=va,
                         year=release.publish_date.year,
                         month=release.publish_date.month,
                         day=release.publish_date.day,
                         label=release.label.name,
                         catalognum=release.catalog_number, media='Digital',
                         data_source=self.data_source, data_url=release.url,
                         genre=None)

    def _get_track_info(self, track):
        """Returns a TrackInfo object for a Beatport Track object.
        """
        title = track.name
        if track.mix_name != "Original Mix":
            title += f" ({track.mix_name})"
        artist, artist_id = self._get_artist(
            ((artist.id, artist.name) for artist in track.artists)
        )
        length = track.length.total_seconds()
        return TrackInfo(title=title, track_id=track.id,
                         artist=artist, artist_id=artist_id,
                         length=length, index=track.number,
                         medium_index=track.number,
                         data_source=self.data_source, data_url=track.url,
                         bpm=track.bpm, initial_key=track.initial_key,
                         genre=track.genre)

    def _get_artist(self, artists):
        """Returns an artist string (all artists) and an artist_id (the main
        artist) for a list of Beatport release or track artists.
        """
        return MetadataSourcePlugin.get_artist(
            artists=artists, id_key=0, name_key=1
        )

    def _get_tracks(self, query):
        """Returns a list of TrackInfo objects for a Beatport query.
        """
        bp_tracks = self.client.search(query, model='tracks')
        tracks = [self._get_track_info(x) for x in bp_tracks]
        return tracks
