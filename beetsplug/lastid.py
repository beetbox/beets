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

class LastIdPlugin(BeetsPlugin):
    def track_distance(self, item, info):
        last_data = match(item.path)
        if not last_data:
            # Match failed.
            return 0.0, 0.0

        dist, dist_max = 0.0, 0.0

        # Track title distance.
        dist += autotag._ie_dist(last_data['title'],
                                info['title']) \
                * autotag.TRACK_TITLE_WEIGHT
        dist_max += autotag.TRACK_TITLE_WEIGHT
        
        # MusicBrainz track ID.
        if last_data['track_mbid']:
            log.debug('Last track ID match: %s/%s' %
                      (last_data['track_mbid'], track_data['id']))
            if last_data['track_mbid'] != track_data['id']:
                dist += autotag.TRACK_ID_WEIGHT
            dist_max += autotag.TRACK_ID_WEIGHT

        log.debug('Last data: %s; distance: %f' %
                  (str(last_data), dist/dist_max))

        return dist * DISTANCE_SCALE, dist_max * DISTANCE_SCALE
