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

from beets.autotag.hooks import AlbumInfo, TrackInfo, Distance
from beets.plugins import BeetsPlugin

log = logging.getLogger('beets')


class BeatportAPIError(Exception):
    pass


class BeatportObject(object):
    def __init__(self, data):
        self.beatport_id = data['id']
        self.name = unicode(data['name'])
        if 'releaseDate' in data:
            self.release_date = datetime.strptime(data['releaseDate'],
                                                  '%Y-%m-%d')
        if 'artists' in data:
            self.artists = [(x['id'], unicode(x['name']))
                            for x in data['artists']]
        if 'genres' in data:
            self.genres = [unicode(x['name'])
                           for x in data['genres']]


class BeatportAPI(object):
    API_BASE = 'http://api.beatport.com/'

    @classmethod
    def get(cls, endpoint, **kwargs):
        try:
            response = requests.get(cls.API_BASE + endpoint, params=kwargs)
        except Exception as e:
            raise BeatportAPIError("Error connection to Beatport API: {}"
                                   .format(e.message))
        if not response:
            raise BeatportAPIError(
                "Error {0.status_code} for '{0.request.path_url}"
                .format(response))
        return response.json()['results']


class BeatportSearch(object):
    query = None
    release_type = None

    def __unicode__(self):
        return u'<BeatportSearch for {0} "{1}" with {2} results>'.format(
            self.release_type, self.query, len(self.results))

    def __init__(self, query, release_type='release', details=True):
        self.results = []
        self.query = query
        self.release_type = release_type
        response = BeatportAPI.get('catalog/3/search', query=query,
                                   facets=['fieldType:{0}'
                                           .format(release_type)],
                                   perPage=5)
        for item in response:
            if release_type == 'release':
                release = BeatportRelease(item)
                if details:
                    release.get_tracks()
                self.results.append(release)
            elif release_type == 'track':
                self.results.append(BeatportTrack(item))


class BeatportRelease(BeatportObject):
    API_ENDPOINT = 'catalog/3/beatport/release'

    def __unicode__(self):
        if len(self.artists) < 4:
            artist_str = ", ".join(x[1] for x in self.artists)
        else:
            artist_str = "Various Artists"
        return u"<BeatportRelease: {0} - {1} ({2})>".format(
            artist_str,
            self.name,
            self.catalog_number,
        )

    def __init__(self, data):
        BeatportObject.__init__(self, data)
        if 'catalogNumber' in data:
            self.catalog_number = data['catalogNumber']
        if 'label' in data:
            self.label_name = data['label']['name']
        if 'category' in data:
            self.category = data['category']
        if 'slug' in data:
            self.url = "http://beatport.com/release/{0}/{1}".format(
                data['slug'], data['id'])

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
    API_ENDPOINT = 'catalog/3/beatport/track'

    def __unicode__(self):
        artist_str = ", ".join(x[1] for x in self.artists)
        return u"<BeatportTrack: {0} - {1} ({2})>".format(artist_str,
                                                          self.name,
                                                          self.mix_name)

    def __init__(self, data):
        BeatportObject.__init__(self, data)
        if 'title' in data:
            self.title = unicode(data['title'])
        if 'mixName' in data:
            self.mix_name = unicode(data['mixName'])
        self.length = timedelta(milliseconds=data.get('lengthMs', 0) or 0)
        if not self.length:
            try:
                min, sec = data.get('length', '0:0').split(':')
                self.length = timedelta(minutes=int(min), seconds=int(sec))
            except ValueError:
                pass
        if 'slug' in data:
            self.url = "http://beatport.com/track/{0}/{1}".format(data['slug'],
                                                                  data['id'])

    @classmethod
    def from_id(cls, beatport_id):
        response = BeatportAPI.get(cls.API_ENDPOINT, id=beatport_id)
        return BeatportTrack(response['track'])


class BeatportPlugin(BeetsPlugin):
    def __init__(self):
        super(BeatportPlugin, self).__init__()
        self.config.add({
            'source_weight': 0.5,
        })

    def album_distance(self, items, album_info, mapping):
        """Returns the beatport source weight and the maximum source weight
        for albums.
        """
        dist = Distance()
        if album_info.data_source == 'Beatport':
            dist.add('source', self.config['source_weight'].as_number())
        return dist

    def track_distance(self, item, track_info):
        """Returns the beatport source weight and the maximum source weight
        for individual tracks.
        """
        dist = Distance()
        if track_info.data_source == 'Beatport':
            dist.add('source', self.config['source_weight'].as_number())
        return dist

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
        match = re.search(r'(^|beatport\.com/release/.+/)(\d+)$', release_id)
        if not match:
            return None
        release = BeatportRelease.from_id(match.group(2))
        album = self._get_album_info(release)
        return album

    def track_for_id(self, track_id):
        """Fetches a track by its Beatport ID and returns a TrackInfo object
        or None if the track is not found.
        """
        log.debug('Searching Beatport for track %s' % str(track_id))
        match = re.search(r'(^|beatport\.com/track/.+/)(\d+)$', track_id)
        if not match:
            return None
        bp_track = BeatportTrack.from_id(match.group(2))
        track = self._get_track_info(bp_track)
        return track

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
        albums = [self._get_album_info(x)
                  for x in BeatportSearch(query).results]
        return albums

    def _get_album_info(self, release):
        """Returns an AlbumInfo object for a Beatport Release object.
        """
        va = len(release.artists) > 3
        artist, artist_id = self._get_artist(release.artists)
        if va:
            artist = u"Various Artists"
        tracks = [self._get_track_info(x, index=idx)
                  for idx, x in enumerate(release.tracks, 1)]

        return AlbumInfo(album=release.name, album_id=release.beatport_id,
                         artist=artist, artist_id=artist_id, tracks=tracks,
                         albumtype=release.category, va=va,
                         year=release.release_date.year,
                         month=release.release_date.month,
                         day=release.release_date.day,
                         label=release.label_name,
                         catalognum=release.catalog_number, media=u'Digital',
                         data_source=u'Beatport', data_url=release.url)

    def _get_track_info(self, track, index=None):
        """Returns a TrackInfo object for a Beatport Track object.
        """
        title = track.name
        if track.mix_name != u"Original Mix":
            title += u" ({0})".format(track.mix_name)
        artist, artist_id = self._get_artist(track.artists)
        length = track.length.total_seconds()

        return TrackInfo(title=title, track_id=track.beatport_id,
                         artist=artist, artist_id=artist_id,
                         length=length, index=index,
                         data_source=u'Beatport', data_url=track.url)

    def _get_artist(self, artists):
        """Returns an artist string (all artists) and an artist_id (the main
        artist) for a list of Beatport release or track artists.
        """
        artist_id = None
        bits = []
        for artist in artists:
            if not artist_id:
                artist_id = artist[0]
            name = artist[1]
            # Strip disambiguation number.
            name = re.sub(r' \(\d+\)$', '', name)
            # Move articles to the front.
            name = re.sub(r'^(.*?), (a|an|the)$', r'\2 \1', name, flags=re.I)
            bits.append(name)
        artist = ', '.join(bits).replace(' ,', ',') or None
        return artist, artist_id

    def _get_tracks(self, query):
        """Returns a list of TrackInfo objects for a Beatport query.
        """
        bp_tracks = BeatportSearch(query, release_type='track').results
        tracks = [self._get_track_info(x) for x in bp_tracks]
        return tracks
