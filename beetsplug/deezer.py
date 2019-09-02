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

"""Adds Deezer release and track search support to the autotagger
"""
from __future__ import absolute_import, print_function

import re
import collections

import six
import unidecode
import requests

from beets import ui
from beets.plugins import BeetsPlugin
from beets.autotag.hooks import AlbumInfo, TrackInfo, Distance


class DeezerPlugin(BeetsPlugin):
    # Base URLs for the Deezer API
    # Documentation: https://developers.deezer.com/api/
    search_url = 'https://api.deezer.com/search/'
    album_url = 'https://api.deezer.com/album/'
    track_url = 'https://api.deezer.com/track/'

    def __init__(self):
        super(DeezerPlugin, self).__init__()
        self.config.add({'source_weight': 0.5})

    def _get_deezer_id(self, url_type, id_):
        """Parse a Deezer ID from its URL if necessary.

        :param url_type: Type of Deezer URL. Either 'album', 'artist',
            'playlist', or 'track'.
        :type url_type: str
        :param id_: Deezer ID or URL.
        :type id_: str
        :return: Deezer ID.
        :rtype: str
        """
        id_regex = r'(^|deezer\.com/([a-z]*/)?{}/)([0-9]*)'
        self._log.debug(u'Searching for {} {}', url_type, id_)
        match = re.search(id_regex.format(url_type), str(id_))
        return match.group(3) if match else None

    def album_for_id(self, album_id):
        """Fetch an album by its Deezer ID or URL and return an
        AlbumInfo object or None if the album is not found.

        :param album_id: Deezer ID or URL for the album.
        :type album_id: str
        :return: AlbumInfo object for album.
        :rtype: beets.autotag.hooks.AlbumInfo or None
        """
        deezer_id = self._get_deezer_id('album', album_id)
        if deezer_id is None:
            return None

        album_data = requests.get(self.album_url + deezer_id).json()
        artist, artist_id = self._get_artist(album_data['contributors'])

        release_date = album_data['release_date']
        date_parts = [int(part) for part in release_date.split('-')]
        num_date_parts = len(date_parts)

        if num_date_parts == 3:
            year, month, day = date_parts
        elif num_date_parts == 2:
            year, month = date_parts
            day = None
        elif num_date_parts == 1:
            year = date_parts[0]
            month = None
            day = None
        else:
            raise ui.UserError(
                u"Invalid `release_date` returned "
                u"by Deezer API: '{}'".format(release_date)
            )

        tracks_data = requests.get(
            self.album_url + deezer_id + '/tracks'
        ).json()['data']
        tracks = []
        medium_totals = collections.defaultdict(int)
        for i, track_data in enumerate(tracks_data):
            track = self._get_track(track_data)
            track.index = i + 1
            medium_totals[track.medium] += 1
            tracks.append(track)
        for track in tracks:
            track.medium_total = medium_totals[track.medium]

        return AlbumInfo(
            album=album_data['title'],
            album_id=deezer_id,
            artist=artist,
            artist_credit=self._get_artist([album_data['artist']]),
            artist_id=artist_id,
            tracks=tracks,
            albumtype=album_data['record_type'],
            va=len(album_data['contributors']) == 1
            and artist.lower() == 'various artists',
            year=year,
            month=month,
            day=day,
            label=album_data['label'],
            mediums=max(medium_totals.keys()),
            data_source='Deezer',
            data_url=album_data['link'],
        )

    def _get_track(self, track_data):
        """Convert a Deezer track object dict to a TrackInfo object.

        :param track_data: Deezer Track object dict
        :type track_data: dict
        :return: TrackInfo object for track
        :rtype: beets.autotag.hooks.TrackInfo
        """
        artist, artist_id = self._get_artist(
            track_data.get('contributors', [track_data['artist']])
        )
        return TrackInfo(
            title=track_data['title'],
            track_id=track_data['id'],
            artist=artist,
            artist_id=artist_id,
            length=track_data['duration'],
            index=track_data['track_position'],
            medium=track_data['disk_number'],
            medium_index=track_data['track_position'],
            data_source='Deezer',
            data_url=track_data['link'],
        )

    def track_for_id(self, track_id=None, track_data=None):
        """Fetch a track by its Deezer ID or URL and return a
        TrackInfo object or None if the track is not found.

        :param track_id: (Optional) Deezer ID or URL for the track. Either
            ``track_id`` or ``track_data`` must be provided.
        :type track_id: str
        :param track_data: (Optional) Simplified track object dict. May be
            provided instead of ``track_id`` to avoid unnecessary API calls.
        :type track_data: dict
        :return: TrackInfo object for track
        :rtype: beets.autotag.hooks.TrackInfo or None
        """
        if track_data is None:
            deezer_id = self._get_deezer_id('track', track_id)
            if deezer_id is None:
                return None
            track_data = requests.get(self.track_url + deezer_id).json()
        track = self._get_track(track_data)

        # Get album's tracks to set `track.index` (position on the entire
        # release) and `track.medium_total` (total number of tracks on
        # the track's disc).
        album_tracks_data = requests.get(
            self.album_url + str(track_data['album']['id']) + '/tracks'
        ).json()['data']
        medium_total = 0
        for i, track_data in enumerate(album_tracks_data, start=1):
            if track_data['disc_number'] == track.medium:
                medium_total += 1
                if track_data['id'] == track.track_id:
                    track.index = i
        track.medium_total = medium_total
        return track

    @staticmethod
    def _get_artist(artists):
        """Returns an artist string (all artists) and an artist_id (the main
        artist) for a list of Deezer artist object dicts.

        :param artists: Iterable of ``contributors`` or ``artist`` returned
            by the Deezer Album (https://developers.deezer.com/api/album) or
            Deezer Track (https://developers.deezer.com/api/track) APIs.
        :type artists: list[dict]
        :return: Normalized artist string
        :rtype: str
        """
        artist_id = None
        artist_names = []
        for artist in artists:
            if not artist_id:
                artist_id = artist['id']
            name = artist['name']
            # Move articles to the front.
            name = re.sub(r'^(.*?), (a|an|the)$', r'\2 \1', name, flags=re.I)
            artist_names.append(name)
        artist = ', '.join(artist_names).replace(' ,', ',') or None
        return artist, artist_id

    def album_distance(self, items, album_info, mapping):
        """Returns the Deezer source weight and the maximum source weight
        for albums.
        """
        dist = Distance()
        if album_info.data_source == 'Deezer':
            dist.add('source', self.config['source_weight'].as_number())
        return dist

    def track_distance(self, item, track_info):
        """Returns the Deezer source weight and the maximum source weight
        for individual tracks.
        """
        dist = Distance()
        if track_info.data_source == 'Deezer':
            dist.add('source', self.config['source_weight'].as_number())
        return dist

    def candidates(self, items, artist, album, va_likely):
        """Returns a list of AlbumInfo objects for Deezer Search API results
        matching an ``album`` and ``artist`` (if not various).

        :param items: List of items comprised by an album to be matched.
        :type items: list[beets.library.Item]
        :param artist: The artist of the album to be matched.
        :type artist: str
        :param album: The name of the album to be matched.
        :type album: str
        :param va_likely: True if the album to be matched likely has
            Various Artists.
        :type va_likely: bool
        :return: Candidate AlbumInfo objects.
        :rtype: list[beets.autotag.hooks.AlbumInfo]
        """
        query_filters = {'album': album}
        if not va_likely:
            query_filters['artist'] = artist
        response_data = self._search_deezer(
            query_type='album', filters=query_filters
        )
        if response_data is None:
            return []
        return [
            self.album_for_id(album_id=album_data['id'])
            for album_data in response_data['data']
        ]

    def item_candidates(self, item, artist, title):
        """Returns a list of TrackInfo objects for Deezer Search API results
        matching ``title`` and ``artist``.

        :param item: Singleton item to be matched.
        :type item: beets.library.Item
        :param artist: The artist of the track to be matched.
        :type artist: str
        :param title: The title of the track to be matched.
        :type title: str
        :return: Candidate TrackInfo objects.
        :rtype: list[beets.autotag.hooks.TrackInfo]
        """
        response_data = self._search_deezer(
            query_type='track', keywords=title, filters={'artist': artist}
        )
        if response_data is None:
            return []
        return [
            self.track_for_id(track_data=track_data)
            for track_data in response_data['data']
        ]

    @staticmethod
    def _construct_search_query(filters=None, keywords=''):
        """Construct a query string with the specified filters and keywords to
        be provided to the Deezer Search API
        (https://developers.deezer.com/api/search).

        :param filters: (Optional) Field filters to apply.
        :type filters: dict
        :param keywords: (Optional) Query keywords to use.
        :type keywords: str
        :return: Query string to be provided to the Search API.
        :rtype: str
        """
        query_components = [
            keywords,
            ' '.join('{}:"{}"'.format(k, v) for k, v in filters.items()),
        ]
        query = ' '.join([q for q in query_components if q])
        if not isinstance(query, six.text_type):
            query = query.decode('utf8')
        return unidecode.unidecode(query)

    def _search_deezer(self, query_type, filters=None, keywords=''):
        """Query the Deezer Search API for the specified ``keywords``, applying
        the provided ``filters``.

        :param query_type: The Deezer Search API method to use. Valid types
            are: 'album', 'artist', 'history', 'playlist', 'podcast',
            'radio', 'track', 'user', and 'track'.
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
        self._log.debug(u"Searching Deezer for '{}'".format(query))
        response_data = requests.get(
            self.search_url + query_type, params={'q': query}
        ).json()
        num_results = len(response_data['data'])
        self._log.debug(
            u"Found {} results from Deezer for '{}'", num_results, query
        )
        return response_data if num_results > 0 else None
