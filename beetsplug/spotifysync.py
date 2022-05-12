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

import re
import json
import base64
import webbrowser
import collections

import unidecode
import requests
import confuse

from beets import ui
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.plugins import MetadataSourcePlugin, BeetsPlugin


class SpotifySyncPlugin(BeetsPlugin):
    data_source = 'Spotify'

    # Base URLs for the Spotify API
    # Documentation: https://developer.spotify.com/web-api
    oauth_token_url = 'https://accounts.spotify.com/api/token'
    open_track_url = 'https://open.spotify.com/track/'
    search_url = 'https://api.spotify.com/v1/search'
    album_url = 'https://api.spotify.com/v1/albums/'
    track_url = 'https://api.spotify.com/v1/tracks/'

    def __init__(self):
        super().__init__()
        self.config.add(
            {
                'show_failures': False,
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
        except OSError:
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
                'Spotify authorization failed: {}\n{}'.format(
                    e, response.text
                )
            )
        self.access_token = response.json()['access_token']

        # Save the token for later use.
        self._log.debug(
            '{} access token: {}', self.data_source, self.access_token
        )
        with open(self.tokenfile, 'w') as f:
            json.dump({'access_token': self.access_token}, f)

    def commands(self):
        cmd = ui.Subcommand('spotifysync',
                            help="fetch track attributes from Spotify")
        cmd.parser.add_option(
            '-f', '--force', dest='force_refetch',
            action='store_true', default=False,
            help='re-download data when already present'
        )

        def func(lib, opts, args):
            items = lib.items(ui.decargs(args))
            self._fetch_info(items, ui.should_write(),
                             opts.force_refetch or self.config['force'])

        cmd.func = func
        return [cmd]

    def _fetch_info(self, items, write, force):
        import time
        """Fetch popularity information from Spotify for the item.
        """
        no_items = len(items)
        self._log.info('Total {} tracks', no_items)

        for index, item in enumerate(items, start=1):
            time.sleep(.5)
            self._log.info('Processing {}/{} tracks - {} ', index, no_items, item)
            try:
                # If we're not forcing re-downloading for all tracks, check
                # whether the popularity data is already present
                if not force:
                    spotify_track_popularity = item.get('spotify_track_popularity', '')
                    if spotify_track_popularity:
                        self._log.debug('Popularity already present for: {}', item)
                        continue

                data = self.track_popularity(item.spotify_track_id)
                if data:
                    self._log.debug('data = {}', data)
                else:
                    self._log.debug('skipping popularity')
                item['spotify_track_popularity'] = data
                item.store()
                if write:
                    item.try_write()
            except AttributeError:
                self._log.debug('No track_id present for: {}', item)
                pass


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
            headers={'Authorization': f'Bearer {self.access_token}'},
            params=params,
        )
        if response.status_code != 200:
            if 'token expired' in response.text:
                self._log.debug(
                    '{} access token has expired. Reauthenticating.',
                    self.data_source,
                )
                self._authenticate()
                return self._handle_response(request_type, url, params=params)
            else:
                raise ui.UserError(
                    '{} API error:\n{}\nURL:\n{}\nparams:\n{}'.format(
                        self.data_source, response.text, url, params
                    )
                )
        return response.json()

    def track_popularity(self, track_id=None):
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
        track_data = self._handle_response(
            requests.get, self.track_url + track_id
        )
        self._log.debug('track_data: {}',track_data['popularity'])
        track_popularity=track_data['popularity']
        return track_popularity

    def _get_track(self, track_data):
        """Convert a Spotify track object dict to a TrackInfo object.

        :param track_data: Simplified track object
            (https://developer.spotify.com/documentation/web-api/reference/object-model/#track-object-simplified)
        :type track_data: dict
        :return: TrackInfo object for track
        :rtype: beets.autotag.hooks.TrackInfo
        """
        return TrackInfo(
            spotify_track_popularity=track_data['popularity'],
        )
