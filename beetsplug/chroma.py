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

"""Adds Chromaprint/Acoustid acoustic fingerprinting support to the
autotagger. Requires the pyacoustid library.
"""
from __future__ import with_statement
from beets import plugins
from beets.autotag import hooks
import acoustid
import logging
from collections import defaultdict

API_KEY = '1vOwZtEn'
SCORE_THRESH = 0.5
TRACK_ID_WEIGHT = 10.0
COMMON_REL_THRESH = 0.6 # How many tracks must have an album in common?

log = logging.getLogger('beets')

class _cached(object):
    """Decorator implementing memoization."""
    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args, **kwargs):
        cache_key = (args, tuple(sorted(kwargs.iteritems())))
        if cache_key in self.cache:
            return self.cache[cache_key]
        res = self.func(*args, **kwargs)
        self.cache[cache_key] = res
        return res

@_cached
def acoustid_match(path, metadata=None):
    """Gets metadata for a file from Acoustid. Returns a recording ID
    and a list of release IDs if a match is found; otherwise, returns
    None.
    """
    try:
        res = acoustid.match(API_KEY, path, meta='recordings releases',
                             parse=False)
    except acoustid.AcoustidError, exc:
        log.debug('fingerprint matching %s failed: %s' % 
                  (repr(path), str(exc)))
        return None
    log.debug('fingerprinted: %s' % repr(path))
    
    # Ensure the response is usable and parse it.
    if res['status'] != 'ok' or not res.get('results'):
        return None
    result = res['results'][0]
    if result['score'] < SCORE_THRESH or not result.get('recordings'):
        return None
    recording = result['recordings'][0]
    recording_id = recording['id']
    if 'releases' in recording:
        release_ids = [rel['id'] for rel in recording['releases']]
    else:
        release_ids = []

    return recording_id, release_ids

def _all_releases(items):
    """Given an iterable of Items, determines (according to Acoustid)
    which releases the items have in common. Generates release IDs.
    """
    # Count the number of "hits" for each release.
    relcounts = defaultdict(int)
    for item in items:
        aidata = acoustid_match(item.path)
        if not aidata:
            continue
        _, release_ids = aidata
        for release_id in release_ids:
            relcounts[release_id] += 1

    for release_id, count in relcounts.iteritems():
        if float(count) / len(items) > COMMON_REL_THRESH:
            yield release_id

class AcoustidPlugin(plugins.BeetsPlugin):
    def track_distance(self, item, info):
        aidata = acoustid_match(item.path)
        if not aidata:
            # Match failed.
            return 0.0, 0.0

        recording_id, _ = aidata
        if info.track_id == recording_id:
            dist = 0.0
        else:
            dist = TRACK_ID_WEIGHT
        return dist, TRACK_ID_WEIGHT

    def candidates(self, items):
        albums = []
        for relid in _all_releases(items):
            album = hooks._album_for_id(relid)
            if album:
                albums.append(album)

        log.debug('acoustid album candidates: %i' % len(albums))
        return albums

    def item_candidates(self, item):
        aidata = acoustid_match(item.path)
        if not aidata:
            return []
        recording_id, _ = aidata
        track = hooks._track_for_id(recording_id)
        if track:
            log.debug('found acoustid item candidate')
            return [track]
        else:
            log.debug('no acoustid item candidate found')
