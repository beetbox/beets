# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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
import logging
import re
from datetime import datetime, timedelta

import requests

from beets import config
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.autotag.match import current_metadata
from beets.plugins import BeetsPlugin

log = logging.getLogger('beets')

# Distance parameters.
BEATPORT_SOURCE_WEIGHT = config['beatport']['source_weight'].as_number()
SOURCE_WEIGHT = config['match']['weight']['source'].as_number()


class BeatportAPIError(Exception):
    pass


class BeatportObject(object):
    beatport_id = None
    name = None
    release_date = None
    artists = []
    genres = []

    def __init__(self, data):
        self.beatport_id = data['id']
        self.name = data['name']
        if 'releaseDate' in data:
            self.release_date = datetime.strptime(data['releaseDate'],
                                                  '%Y-%m-%d')
        if 'artists' in data:
            self.artists = [x['name'] for x in data['artists']]
        if 'genres' in data:
            self.genres = [x['name'] for x in data['genres']]


class BeatportAPI(object):
    API_BASE = 'http://api.beatport.com/'

    @classmethod
    def get(cls, endpoint, **kwargs):
        response = requests.get(cls.API_BASE + endpoint, params=kwargs)
        if not response:
            raise BeatportAPIError(
                "Error {.status_code} for '{.request.path_url}"
                .format(response))
        return response.json()['results']


class BeatportSearch(object):
    query = None
    release_type = None
    results = []

    def __unicode__(self):
        return u"<BeatportSearch for {} \"{}\" with {} results>".format(
            self.release_type, self.query, len(self.results))

    def __init__(self, query, release_type='release', details=True):
        self.query = query
        self.release_type = release_type
        results = BeatportAPI.get('catalog/3/search', query=query,
                                  facets=['fieldType:{}'.format(release_type)],
                                  perPage=5)
        for item in results:
            if release_type == 'release':
                self.results.append(BeatportRelease(item))
            elif release_type == 'track':
                self.results.append(BeatportTrack(item))
            if details:
                self.results[-1].get_tracks()


class BeatportRelease(BeatportObject):
    API_ENDPOINT = 'catalog/3/beatport/release'
    catalog_number = None
    label_name = None
    tracks = []

    def __unicode__(self):
        if len(self.artists) < 4:
            artist_str = ", ".join(self.artists)
        else:
            artist_str = "Various Artists"
        return u"<BeatportRelease: {} - {} ({})>".format(artist_str, self.name,
                                                         self.catalog_number)

    def __init__(self, data):
        BeatportObject.__init__(self, data)
        if 'catalogNumber' in data:
            self.catalog_number = data['catalogNumber']
        if 'label' in data:
            self.label_name = data['label']['name']

    @classmethod
    def from_id(cls, beatport_id):
        response = BeatportAPI.get(cls.API_ENDPOINT, id=beatport_id)
        release = BeatportRelease(response['release'])
        release.tracks = [BeatportTrack(x) for x in response['tracks']]
        return release

    def get_tracks(self):
        response = BeatportAPI.get(self.API_ENDPOINT, id=self.beatport_id)
        self.tracks = [BeatportTrack(x) for x in response['tracks']]


class BeatportTrack(BeatportObject):
    API_ENDPOINT = 'catalog/3/beatport/release'
    title = None
    mix_name = None
    length = None

    def __unicode__(self):
        artist_str = ", ".join(self.artists)
        return u"<BeatportTrack: {} - {} ({})>".format(artist_str, self.name,
                                                       self.mix_name)

    def __init__(self, data):
        BeatportObject.__init__(self, data)
        if 'title' in data:
            self.title = data['title']
        if 'mixName' in data:
            self.mix_name = data['mixName']
        if 'length' in data:
            self.length = timedelta(milliseconds=data['lengthMs'])

    @classmethod
    def from_id(cls, beatport_id):
        response = BeatportAPI.get(cls.API_ENDPOINT, id=beatport_id)
        return BeatportTrack(response['track'])


class BeatportPlugin(BeetsPlugin):
    def album_distance(self, items, album_info, mapping):
        """Returns the beatport source weight and the maximum source weight
        for albums.
        """
        return BEATPORT_SOURCE_WEIGHT * SOURCE_WEIGHT, SOURCE_WEIGHT

    def track_distance(self, item, info):
        """Returns the beatport source weight and the maximum source weight
        for individual tracks.
        """
        return BEATPORT_SOURCE_WEIGHT * SOURCE_WEIGHT, SOURCE_WEIGHT

    def candidates(self, items, artist, release, va_likely):
        """Returns a list of AlbumInfo objects for beatport search results
        matching release and artist (if not various).
        """
        if va_likely:
            query = release
        else:
            query = '%s %s' % (artist, release)
        try:
            return self._get_releases(query)
        except BeatportAPIError as e:
            log.debug('Beatport API Error: %s (query: %s)' % (e, query))
            return []

    def item_candidates(self, item, artist, title):
        """Returns a list of TrackInfo objects for beatport search results
        matching title and artist.
        """
        query = '%s %s' % (artist, title)
        try:
            return self._get_tracks(query)
        except BeatportAPIError as e:
            log.debug('Beatport API Error: %s (query: %s)' % (e, query))
            return []

    def album_for_id(self, release_id):
        """Fetches a release by its Beatport ID and returns an AlbumInfo object
        or None if the release is not found.
        """
        log.debug('Searching Beatport for release %s' % str(release_id))
        # TODO: Verify that release_id is a valid Beatport release ID
        # TODO: Obtain release from Beatport
        # TODO: Return an AlbumInfo object generated from the BeatporRelease
        raise NotImplementedError

    def track_for_id(self, track_id):
        """Fetches a track by its Beatport ID and returns a TrackInfo object
        or None if the track is not found.
        """
        log.debug('Searching Beatport for track %s' % str(track_id))
        # TODO: Verify that release_id is a valid Beatport track ID
        # TODO: Obtain track from Beatport
        # TODO: Return a TrackInfo object generated from the BeatportTrack
        raise NotImplementedError

    def _get_releases(self, query):
        """Returns a list of AlbumInfo objects for a beatport search query.
        """
        # Strip non-word characters from query. Things like "!" and "-" can
        # cause a query to return no results, even if they match the artist or
        # album title. Use `re.UNICODE` flag to avoid stripping non-english
        # word characters.
        query = re.sub(r'\W+', ' ', query, re.UNICODE)
        # Strip medium information from query, Things like "CD1" and "disk 1"
        # can also negate an otherwise positive result.
        query = re.sub(r'\b(CD|disc)\s*\d+', '', query, re.I)
        albums = []
        # TODO: Obtain search results from Beatport (count=5)
        # TODO: Generate AlbumInfo object for each item in the results and
        #       return them in a list
        raise NotImplementedError

    def _get_album_info(self, result):
        """Returns an AlbumInfo object for a Beatport Release object.
        """
        raise NotImplementedError

    def _get_track_info(self, result):
        """Returns a TrackInfo object for a Beatport Track object.
        """
        raise NotImplementedError

    def _get_artist(self, artists):
        """Returns an artist string (all artists) and an artist_id (the main
        artist) for a list of Beatport release or track artists.
        """
        artist_id = None
        bits = []
        for artist in artists:
            if not artist_id:
                artist_id = artist['id']
            name = artist['name']
            # Strip disambiguation number.
            name = re.sub(r' \(\d+\)$', '', name)
            # Move articles to the front.
            name = re.sub(r'^(.*?), (a|an|the)$', r'\2 \1', name, flags=re.I)
            bits.append(name)
            if artist['join']:
                bits.append(artist['join'])
        artist = ' '.join(bits).replace(' ,', ',') or None
        return artist, artist_id

    def _get_tracks(self, tracklist):
        """Returns a list of TrackInfo objects for a list of Beatport Track
        objects.
        """
        tracks = []
        for track in tracklist:
            # TODO: Generate TrackInfo object from Beatport Track object and
            #       add it to the list of tracks
            pass
        raise NotImplementedError
