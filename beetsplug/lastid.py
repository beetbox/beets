# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

"""Adds Last.fm acoustic fingerprinting support to the autotagger.
Requires the pylastfp library.
"""

from __future__ import with_statement
from beets.plugins import BeetsPlugin
from beets import autotag
from beets.autotag import mb
from beets.util import plurality
import lastfp
import logging

API_KEY = '2dc3914abf35f0d9c92d97d8f8e42b43'

# The amplification factor for distances calculated from fingerprinted
# data. With this set to 2.0, for instance, "fingerprinted" track titles
# will be considered twice as important as track titles from ID3 tags.
DISTANCE_SCALE = 2.0

log = logging.getLogger('beets')

_match_cache = {}
def match(path, metadata=None):
    """Gets the metadata from Last.fm for the indicated track. Returns
    a dictionary with these keys: rank, artist, artist_mbid, title,
    track_mbid. May return None if fingerprinting or lookup fails.
    Caches the result, so multiple calls may be made efficiently.
    """
    if path in _match_cache:
        return _match_cache[path]

    # Actually perform fingerprinting and lookup.
    try:
        xml = lastfp.gst_match(API_KEY, path, metadata)
        matches = lastfp.parse_metadata(xml)
    except lastfp.FingerprintError:
        # Fail silently and cache the failure.
        matches = None
    match = matches[0] if matches else None

    _match_cache[path] = match
    return match

def get_cur_artist(items):
    """Given a sequence of items, returns the current artist and
    artist ID that is most popular among the fingerprinted metadata
    for the tracks.
    """
    # Get "fingerprinted" artists for each track.
    artists = []
    artist_ids = []
    for item in items:
        last_data = match(item.path)
        if last_data:
            artists.append(last_data['artist'])
            if last_data['artist_mbid']:
                artist_ids.append(last_data['artist_mbid'])

    # Vote on the most popular artist.
    artist, _ = plurality(artists)
    artist_id, _ = plurality(artist_ids)

    return artist, artist_id

class LastIdPlugin(BeetsPlugin):
    def track_distance(self, item, info):
        last_data = match(item.path)
        if not last_data:
            # Match failed.
            return 0.0, 0.0

        dist, dist_max = 0.0, 0.0

        # Track title distance.
        dist += autotag.string_dist(last_data['title'],
                                 info['title']) \
                * autotag.TRACK_TITLE_WEIGHT
        dist_max += autotag.TRACK_TITLE_WEIGHT
        
        # MusicBrainz track ID.
        if last_data['track_mbid']:
            # log.debug('Last track ID match: %s/%s' %
            #           (last_data['track_mbid'], track_data['id']))
            if last_data['track_mbid'] != track_data['id']:
                dist += autotag.TRACK_ID_WEIGHT
            dist_max += autotag.TRACK_ID_WEIGHT

        # log.debug('Last data: %s; distance: %f' %
        #           (str(last_data), dist/dist_max if dist_max > 0.0 else 0.0))

        return dist * DISTANCE_SCALE, dist_max * DISTANCE_SCALE

    def album_distance(self, items, info):
        last_artist, last_artist_id = get_cur_artist(items)

        # Compare artist to MusicBrainz metadata.
        dist, dist_max = 0.0, 0.0
        if last_artist:
            dist += autotag.string_dist(last_artist, info['artist']) \
                    * autotag.ARTIST_WEIGHT
            dist_max += autotag.ARTIST_WEIGHT

        log.debug('Last artist (%s/%s) distance: %f' %
                  (last_artist, info['artist'],
                   dist/dist_max if dist_max > 0.0 else 0.0))

        #fixme: artist MBID currently ignored (as in vanilla tagger)
        return dist, dist_max

    def candidates(self, items):
        last_artist, last_artist_id = get_cur_artist(items)

        # Build the search criteria. Use the artist ID if we have one;
        # otherwise use the artist name. Unfortunately, Last.fm doesn't
        # give us album information.
        criteria = {'trackCount': len(items)}
        if last_artist_id:
            criteria['artistId'] = last_artist_id
        else:
            criteria['artistName'] = last_artist

        # Perform the search.
        criteria['limit'] = autotag.MAX_CANDIDATES
        cands = list(mb.get_releases(**criteria))

        log.debug('Matched last candidates: %s' %
                  ', '.join([cand['album'] for cand in cands]))
        return cands

    def item_candidates(self, item):
        last_data = match(item.path)
        if not last_data:
            return ()

        # Have a MusicBrainz track ID?
        if last_data['track_mbid']:
            log.debug('Have a track ID from last.fm: %s' %
                      last_data['track_mbid'])
            id_track = mb.track_for_id(last_data['track_mbid'])
            if id_track:
                log.debug('Matched by track ID.')
                return (id_track,)

        # Do a full search.
        criteria = {
            'artist': last_data['artist'],
            'track': last_data['title'],
        }
        if last_data['artist_mbid']:
            criteria['artistid'] = last_data['artist_mbid']
        cands = list(mb.find_tracks(criteria))

        log.debug('Matched last track candidates: %s' %
                  ', '.join([cand['title'] for cand in cands]))
        return cands
