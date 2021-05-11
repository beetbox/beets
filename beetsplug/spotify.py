# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2019, Rahul Ahuja.
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

"""Adds Spotify release and track search support to the autotagger, along with
Spotify playlist construction.
"""
from __future__ import division, absolute_import, print_function

import re
import json
import base64
import webbrowser
import collections

import six
import unidecode
import requests
import confuse

from beets import ui
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.plugins import MetadataSourcePlugin, BeetsPlugin


class SpotifyPlugin(MetadataSourcePlugin, BeetsPlugin):
    data_source = 'Spotify'

    # Base URLs for the Spotify API
    # Documentation: https://developer.spotify.com/web-api
    oauth_token_url = 'https://accounts.spotify.com/api/token'
    open_track_url = 'https://open.spotify.com/track/'
    search_url = 'https://api.spotify.com/v1/search'
    album_url = 'https://api.spotify.com/v1/albums/'
    track_url = 'https://api.spotify.com/v1/tracks/'

    # Spotify IDs consist of 22 alphanumeric characters
    # (zero-left-padded base62 representation of randomly generated UUID4)
    id_regex = {
        'pattern': r'(^|open\.spotify\.com/{}/)([0-9A-Za-z]{{22}})',
        'match_group': 2,
    }

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
                'client_id': '4e414367a1d14c75a5c5129a627fcab8',
                'client_secret': 'f82bdc09b2254f1a8286815d02fd46dc',
                'tokenfile': 'spotify_token.json',
            }
        )
        self.config['client_secret'].redact = True

        self.tokenfile = self.config['tokenfile'].get(
            confuse.Filename(in_app_dir=True)
        )  # Path to the JSON file for storing the OAuth access token.
        self.setup()

    def setup(self):
        """Retrieve previously saved OAuth token or generate a new one."""
        try:
            with open(self.tokenfile) as f:
                token_data = json.load(f)
        except IOError:
            self._authenticate()
        else:
            self.access_token = token_data['access_token']

    def _authenticate(self):
        """Request an access token via the Client Credentials Flow:
        https://developer.spotify.com/documentation/general/guides/authorization-guide/#client-credentials-flow
        """
        headers = {
            'Authorization': 'Basic {}'.format(
                base64.b64encode(
                    ':'.join(
                        self.config[k].as_str()
                        for k in ('client_id', 'client_secret')
                    ).encode()
                ).decode()
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
                    e, response.text
                )
            )
        self.access_token = response.json()['access_token']

        # Save the token for later use.
        self._log.debug(
            u'{} access token: {}', self.data_source, self.access_token
        )
        with open(self.tokenfile, 'w') as f:
            json.dump({'access_token': self.access_token}, f)

    def _handle_response(self, request_type, url, params=None):
        """Send a request, reauthenticating if necessary.

        :param request_type: Type of :class:`Request` constructor,
            e.g. ``requests.get``, ``requests.post``, etc.
        :type request_type: function
        :param url: URL for the new :class:`Request` object.
        :type url: str
        :param params: (optional) list of tuples or bytes to send
            in the query string for the :class:`Request`.
        :type params: dict
        :return: JSON data for the class:`Response <Response>` object.
        :rtype: dict
        """
        response = request_type(
            url,
            headers={'Authorization': 'Bearer {}'.format(self.access_token)},
            params=params,
        )
        if response.status_code != 200:
            if u'token expired' in response.text:
                self._log.debug(
                    '{} access token has expired. Reauthenticating.',
                    self.data_source,
                )
                self._authenticate()
                return self._handle_response(request_type, url, params=params)
            else:
                raise ui.UserError(
                    u'{} API error:\n{}\nURL:\n{}\nparams:\n{}'.format(
                        self.data_source, response.text, url, params
                    )
                )
        return response.json()

    def album_for_id(self, album_id):
        """Fetch an album by its Spotify ID or URL and return an
        AlbumInfo object or None if the album is not found.

        :param album_id: Spotify ID or URL for the album
        :type album_id: str
        :return: AlbumInfo object for album
        :rtype: beets.autotag.hooks.AlbumInfo or None
        """
        spotify_id = self._get_id('album', album_id)
        if spotify_id is None:
            return None

        album_data = self._handle_response(
            requests.get, self.album_url + spotify_id
        )
        artist, artist_id = self.get_artist(album_data['artists'])

        date_parts = [
            int(part) for part in album_data['release_date'].split('-')
        ]

        release_date_precision = album_data['release_date_precision']
        if release_date_precision == 'day':
            year, month, day = date_parts
        elif release_date_precision == 'month':
            year, month = date_parts
            day = None
        elif release_date_precision == 'year':
            year = date_parts[0]
            month = None
            day = None
        else:
            raise ui.UserError(
                u"Invalid `release_date_precision` returned "
                u"by {} API: '{}'".format(
                    self.data_source, release_date_precision
                )
            )

        tracks = []
        medium_totals = collections.defaultdict(int)
        for i, track_data in enumerate(album_data['tracks']['items'], start=1):
            track = self._get_track(track_data)
            track.index = i
            medium_totals[track.medium] += 1
            tracks.append(track)
        for track in tracks:
            track.medium_total = medium_totals[track.medium]

        return AlbumInfo(
            album=album_data['name'],
            album_id=spotify_id,
            artist=artist,
            artist_id=artist_id,
            tracks=tracks,
            albumtype=album_data['album_type'],
            va=len(album_data['artists']) == 1
            and artist.lower() == 'various artists',
            year=year,
            month=month,
            day=day,
            label=album_data['label'],
            mediums=max(medium_totals.keys()),
            data_source=self.data_source,
            data_url=album_data['external_urls']['spotify'],
        )

    def _get_track(self, track_data):
        """Convert a Spotify track object dict to a TrackInfo object.

        :param track_data: Simplified track object
            (https://developer.spotify.com/documentation/web-api/reference/object-model/#track-object-simplified)
        :type track_data: dict
        :return: TrackInfo object for track
        :rtype: beets.autotag.hooks.TrackInfo
        """
        artist, artist_id = self.get_artist(track_data['artists'])
        return TrackInfo(
            title=track_data['name'],
            track_id=track_data['id'],
            artist=artist,
            artist_id=artist_id,
            length=track_data['duration_ms'] / 1000,
            index=track_data['track_number'],
            medium=track_data['disc_number'],
            medium_index=track_data['track_number'],
            data_source=self.data_source,
            data_url=track_data['external_urls']['spotify'],
        )

    def track_for_id(self, track_id=None, track_data=None):
        """Fetch a track by its Spotify ID or URL and return a
        TrackInfo object or None if the track is not found.

        :param track_id: (Optional) Spotify ID or URL for the track. Either
            ``track_id`` or ``track_data`` must be provided.
        :type track_id: str
        :param track_data: (Optional) Simplified track object dict. May be
            provided instead of ``track_id`` to avoid unnecessary API calls.
        :type track_data: dict
        :return: TrackInfo object for track
        :rtype: beets.autotag.hooks.TrackInfo or None
        """
        if track_data is None:
            spotify_id = self._get_id('track', track_id)
            if spotify_id is None:
                return None
            track_data = self._handle_response(
                requests.get, self.track_url + spotify_id
            )
        track = self._get_track(track_data)

        # Get album's tracks to set `track.index` (position on the entire
        # release) and `track.medium_total` (total number of tracks on
        # the track's disc).
        album_data = self._handle_response(
            requests.get, self.album_url + track_data['album']['id']
        )
        medium_total = 0
        for i, track_data in enumerate(album_data['tracks']['items'], start=1):
            if track_data['disc_number'] == track.medium:
                medium_total += 1
                if track_data['id'] == track.track_id:
                    track.index = i
        track.medium_total = medium_total
        return track

    @staticmethod
    def _construct_search_query(filters=None, keywords=''):
        """Construct a query string with the specified filters and keywords to
        be provided to the Spotify Search API
        (https://developer.spotify.com/documentation/web-api/reference/search/search/#writing-a-query---guidelines).

        :param filters: (Optional) Field filters to apply.
        :type filters: dict
        :param keywords: (Optional) Query keywords to use.
        :type keywords: str
        :return: Query string to be provided to the Search API.
        :rtype: str
        """
        query_components = [
            keywords,
            ' '.join(':'.join((k, v)) for k, v in filters.items()),
        ]
        query = ' '.join([q for q in query_components if q])
        if not isinstance(query, six.text_type):
            query = query.decode('utf8')
        return unidecode.unidecode(query)

    def _search_api(self, query_type, filters=None, keywords=''):
        """Query the Spotify Search API for the specified ``keywords``, applying
        the provided ``filters``.

        :param query_type: Item type to search across. Valid types are:
            'album', 'artist', 'playlist', and 'track'.
        :type query_type: str
        :param filters: (Optional) Field filters to apply.
        :type filters: dict
        :param keywords: (Optional) Query keywords to use.
        :type keywords: str
        :return: JSON data for the class:`Response <Response>` object or None
            if no search results are returned.
        :rtype: dict or None
        """
        query = self._construct_search_query(
            keywords=keywords, filters=filters
        )
        if not query:
            return None
        self._log.debug(
            u"Searching {} for '{}'".format(self.data_source, query)
        )
        response_data = (
            self._handle_response(
                requests.get,
                self.search_url,
                params={'q': query, 'type': query_type},
            )
            .get(query_type + 's', {})
            .get('items', [])
        )
        self._log.debug(
            u"Found {} result(s) from {} for '{}'",
            len(response_data),
            self.data_source,
            query,
        )
        return response_data

    def commands(self):
        def queries(lib, opts, args):
            success = self._parse_opts(opts)
            if success:
                results = self._match_library_tracks(lib, ui.decargs(args))
                self._output_match_results(results)

        spotify_cmd = ui.Subcommand(
            'spotify', help=u'build a {} playlist'.format(self.data_source)
        )
        spotify_cmd.parser.add_option(
            u'-m',
            u'--mode',
            action='store',
            help=u'"open" to open {} with playlist, '
            u'"list" to print (default)'.format(self.data_source),
        )
        spotify_cmd.parser.add_option(
            u'-f',
            u'--show-failures',
            action='store_true',
            dest='show_failures',
            help=u'list tracks that did not match a {} ID'.format(
                self.data_source
            ),
        )
        spotify_cmd.func = queries
        return [spotify_cmd]

    def _parse_opts(self, opts):
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

    def _match_library_tracks(self, library, keywords):
        """Get a list of simplified track object dicts for library tracks
        matching the specified ``keywords``.

        :param library: beets library object to query.
        :type library: beets.library.Library
        :param keywords: Query to match library items against.
        :type keywords: str
        :return: List of simplified track object dicts for library items
            matching the specified query.
        :rtype: list[dict]
        """
        results = []
        failures = []

        items = library.items(keywords)

        if not items:
            self._log.debug(
                u'Your beets query returned no items, skipping {}.',
                self.data_source,
            )
            return

        self._log.info(u'Processing {} tracks...', len(items))

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
            keywords = item[self.config['track_field'].get()]

            # Query the Web API for each track, look for the items' JSON data
            query_filters = {'artist': artist, 'album': album}
            response_data_tracks = self._search_api(
                query_type='track', keywords=keywords, filters=query_filters
            )
            if not response_data_tracks:
                query = self._construct_search_query(
                    keywords=keywords, filters=query_filters
                )
                failures.append(query)
                continue

            # Apply market filter if requested
            region_filter = self.config['region_filter'].get()
            if region_filter:
                response_data_tracks = [
                    track_data
                    for track_data in response_data_tracks
                    if region_filter in track_data['available_markets']
                ]

            if (
                len(response_data_tracks) == 1
                or self.config['tiebreak'].get() == 'first'
            ):
                self._log.debug(
                    u'{} track(s) found, count: {}',
                    self.data_source,
                    len(response_data_tracks),
                )
                chosen_result = response_data_tracks[0]
            else:
                # Use the popularity filter
                self._log.debug(
                    u'Most popular track chosen, count: {}',
                    len(response_data_tracks),
                )
                chosen_result = max(
                    response_data_tracks, key=lambda x: x['popularity']
                )
            results.append(chosen_result)

        failure_count = len(failures)
        if failure_count > 0:
            if self.config['show_failures'].get():
                self._log.info(
                    u'{} track(s) did not match a {} ID:',
                    failure_count,
                    self.data_source,
                )
                for track in failures:
                    self._log.info(u'track: {}', track)
                self._log.info(u'')
            else:
                self._log.warning(
                    u'{} track(s) did not match a {} ID:\n'
                    u'use --show-failures to display',
                    failure_count,
                    self.data_source,
                )

        return results

    def _output_match_results(self, results):
        """Open a playlist or print Spotify URLs for the provided track
        object dicts.

        :param results: List of simplified track object dicts
            (https://developer.spotify.com/documentation/web-api/reference/object-model/#track-object-simplified)
        :type results: list[dict]
        """
        if results:
            spotify_ids = [track_data['id'] for track_data in results]
            if self.config['mode'].get() == 'open':
                self._log.info(
                    u'Attempting to open {} with playlist'.format(
                        self.data_source
                    )
                )
                spotify_url = 'spotify:trackset:Playlist:' + ','.join(
                    spotify_ids
                )
                webbrowser.open(spotify_url)
            else:
                for spotify_id in spotify_ids:
                    print(self.open_track_url + spotify_id)
        else:
            self._log.warning(
                u'No {} tracks found from beets query'.format(self.data_source)
            )
