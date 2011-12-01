# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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
from beets import plugins
from beets.autotag import mb
from beets.autotag import match
from beets.util import plurality
import lastfp
import logging

# The amplification factor for distances calculated from fingerprinted
# data. With this set to 2.0, for instance, "fingerprinted" track titles
# will be considered twice as important as track titles from ID3 tags.
DISTANCE_SCALE = 2.0

log = logging.getLogger('beets')

_match_cache = {}
def last_match(path, metadata=None):
    """Gets the metadata from Last.fm for the indicated track. Returns
    a dictionary with these keys: rank, artist, artist_mbid, title,
    track_mbid. May return None if fingerprinting or lookup fails.
    Caches the result, so multiple calls may be made efficiently.
    """
    if path in _match_cache:
        return _match_cache[path]

    # Actually perform fingerprinting and lookup.
    try:
        xml = lastfp.gst_match(plugins.LASTFM_KEY, path, metadata)
        matches = lastfp.parse_metadata(xml)
    except lastfp.FingerprintError:
        # Fail silently and cache the failure.
        matches = None
    top_match = matches[0] if matches else None

    _match_cache[path] = top_match
    return top_match

def get_cur_artist(items):
    """Given a sequence of items, returns the current artist and
    artist ID that is most popular among the fingerprinted metadata
    for the tracks.
    """
    # Get "fingerprinted" artists for each track.
    artists = []
    artist_ids = []
    for item in items:
        last_data = last_match(item.path)
        if last_data:
            artists.append(last_data['artist'])
            if last_data['artist_mbid']:
                artist_ids.append(last_data['artist_mbid'])

    # Vote on the most popular artist.
    artist, _ = plurality(artists)
    artist_id, _ = plurality(artist_ids)

    return artist, artist_id

class LastIdPlugin(plugins.BeetsPlugin):
    def track_distance(self, item, info):
        last_data = last_match(item.path)
        if not last_data:
            # Match failed.
            return 0.0, 0.0

        dist, dist_max = 0.0, 0.0

        # Track title distance.
        dist += match.string_dist(last_data['title'],
                                  info['title']) \
                * match.TRACK_TITLE_WEIGHT
        dist_max += match.TRACK_TITLE_WEIGHT
        
        # MusicBrainz track ID.
        if last_data['track_mbid']:
            # log.debug('Last track ID match: %s/%s' %
            #           (last_data['track_mbid'], track_data['id']))
            if last_data['track_mbid'] != last_data['id']:
                dist += match.TRACK_ID_WEIGHT
            dist_max += match.TRACK_ID_WEIGHT

        # log.debug('Last data: %s; distance: %f' %
        #           (str(last_data), dist/dist_max if dist_max > 0.0 else 0.0))

        return dist * DISTANCE_SCALE, dist_max * DISTANCE_SCALE

    def album_distance(self, items, info):
        last_artist, last_artist_id = get_cur_artist(
            [item for item in items if item]
        )

        # Compare artist to MusicBrainz metadata.
        dist, dist_max = 0.0, 0.0
        if last_artist:
            dist += match.string_dist(last_artist, info['artist']) \
                    * match.ARTIST_WEIGHT
            dist_max += match.ARTIST_WEIGHT

        log.debug('Last artist (%s/%s) distance: %f' %
                  (last_artist, info['artist'],
                   dist/dist_max if dist_max > 0.0 else 0.0))

        #fixme: artist MBID currently ignored (as in vanilla tagger)
        return dist, dist_max

    def candidates(self, items):
        last_artist, last_artist_id = get_cur_artist(items)

        # Search MusicBrainz based on Last.fm metadata.
        cands = list(mb.match_album(last_artist, '', len(items)))

        log.debug('Matched last candidates: %s' %
                  ', '.join([cand['album'] for cand in cands]))
        return cands

    def item_candidates(self, item):
        last_data = last_match(item.path)
        if not last_data:
            return ()

        # Search MusicBrainz.
        cands = list(mb.match_track(last_data['artist'],
                                    last_data['track']))

        log.debug('Matched last track candidates: %s' %
                  ', '.join([cand['title'] for cand in cands]))
        return cands
