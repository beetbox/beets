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
from beets import config
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.autotag.match import current_metadata, VA_ARTISTS
from beets.plugins import BeetsPlugin

import beets
import discogs_client
import logging
import re
import time

log = logging.getLogger('beets')

# Distance parameters.
DISCOGS_SOURCE_WEIGHT = config['beatport']['source_weight'].as_number()
SOURCE_WEIGHT = config['match']['weight']['source'].as_number()

class BeatportAPIError(Exception):
    pass

class BeatportRelease(object):
    pass

class BeatportTrack(object):
    pass

class BeatportPlugin(BeetsPlugin):
    def album_distance(self, items, album_info, mapping):
        """Returns the beatport source weight and the maximum source weight
        for albums.
        """
        return DISCOGS_SOURCE_WEIGHT * SOURCE_WEIGHT, SOURCE_WEIGHT

    def track_distance(self, item, info):
        """Returns the beatport source weight and the maximum source weight
        for individual tracks.
        """
        return DISCOGS_SOURCE_WEIGHT * SOURCE_WEIGHT, SOURCE_WEIGHT

    def candidates(self, items, artist, release, va_likely):
        """Returns a list of AlbumInfo objects for beatport search results
        matching release and artist (if not various).
        """
        if va_likely:
            query = album
        else:
            query = '%s %s' % (artist, album)
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
        log.debug('Searching Beatport for release %s' % str(album_id))
        # TODO: Verify that release_id is a valid Beatport release ID
        # TODO: Obtain release from Beatport
        # TODO: Return an AlbumInfo object generated from the Beatport release
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
