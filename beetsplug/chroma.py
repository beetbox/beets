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
from beets import ui
from beets import util
from beets.autotag import hooks
import acoustid
import logging
from collections import defaultdict

API_KEY = '1vOwZtEn'
SCORE_THRESH = 0.5
TRACK_ID_WEIGHT = 10.0
COMMON_REL_THRESH = 0.6 # How many tracks must have an album in common?

log = logging.getLogger('beets')

# Stores the Acoustid match information for each track. This is
# populated when an import task begins and then used when searching for
# candidates. It maps audio file paths to (recording_id, release_ids)
# pairs. If a given path is not present in the mapping, then no match
# was found.
_matches = {}

# Stores the fingerprint and Acoustid ID for each track. This is stored
# as metadata for each track for later use but is not relevant for
# autotagging.
_fingerprints = {}
_acoustids = {}

# The user's Acoustid API key, if provided.
_userkey = None


def acoustid_match(path):
    """Gets metadata for a file from Acoustid and populates the
    _matches, _fingerprints, and _acoustids dictionaries accordingly.
    """
    try:
        duration, fp = acoustid.fingerprint_file(path)
    except acoustid.FingerprintGenerationError, exc:
        log.error('fingerprinting of %s failed: %s' %
                  (repr(path), str(exc)))
        return None
    _fingerprints[path] = fp
    try:
        res = acoustid.lookup(API_KEY, fp, duration,
                              meta='recordings releases')
    except acoustid.AcoustidError, exc:
        log.debug('fingerprint matching %s failed: %s' % 
                  (repr(path), str(exc)))
        return None
    log.debug('chroma: fingerprinted %s' % repr(path))
    
    # Ensure the response is usable and parse it.
    if res['status'] != 'ok' or not res.get('results'):
        log.debug('chroma: no match found')
        return None
    result = res['results'][0]
    if result['score'] < SCORE_THRESH:
        log.debug('chroma: no results above threshold')
        return None
    _acoustids[path] = result['id']

    # Get recordings from the result.
    if not result.get('recordings'):
        log.debug('chroma: no recordings found')
        return None
    recording = result['recordings'][0]
    recording_id = recording['id']
    if 'releases' in recording:
        release_ids = [rel['id'] for rel in recording['releases']]
    else:
        release_ids = []

    log.debug('chroma: matched recording {0}'.format(recording_id))
    _matches[path] = recording_id, release_ids


# Plugin structure and autotagging logic.

def _all_releases(items):
    """Given an iterable of Items, determines (according to Acoustid)
    which releases the items have in common. Generates release IDs.
    """
    # Count the number of "hits" for each release.
    relcounts = defaultdict(int)
    for item in items:
        if item.path not in _matches:
            continue

        _, release_ids = _matches[item.path]
        for release_id in release_ids:
            relcounts[release_id] += 1

    for release_id, count in relcounts.iteritems():
        if float(count) / len(items) > COMMON_REL_THRESH:
            yield release_id

class AcoustidPlugin(plugins.BeetsPlugin):
    def track_distance(self, item, info):
        if item.path not in _matches:
            # Match failed.
            return 0.0, 0.0

        recording_id, _ = _matches[item.path]
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
        if item.path not in _matches:
            return []

        recording_id, _ = _matches[item.path]
        track = hooks._track_for_id(recording_id)
        if track:
            log.debug('found acoustid item candidate')
            return [track]
        else:
            log.debug('no acoustid item candidate found')
            return []

    def configure(self, config):
        global _userkey
        _userkey = ui.config_val(config, 'acoustid', 'apikey', None)

    def commands(self):
        submit_cmd = ui.Subcommand('submit',
                                   help='submit Acoustid fingerprints')
        def submit_cmd_func(lib, config, opts, args):
            if not _userkey:
                raise ui.UserError('no Acoustid user API key provided')
            submit_items(_userkey, lib.items(ui.decargs(args)))
        submit_cmd.func = submit_cmd_func
        return [submit_cmd]


# Hooks into import process.

@AcoustidPlugin.listen('import_task_start')
def fingerprint_task(config=None, task=None):
    """Fingerprint each item in the task for later use during the
    autotagging candidate search.
    """
    for item in task.all_items():
        acoustid_match(item.path)

@AcoustidPlugin.listen('import_task_apply')
def apply_acoustid_metadata(config=None, task=None):
    """Apply Acoustid metadata (fingerprint and ID) to the task's items.
    """
    for item in task.all_items():
        if item.path in _fingerprints:
            item.acoustid_fingerprint = _fingerprints[item.path]
        if item.path in _acoustids:
            item.acoustid_id = _acoustids[item.path]


# UI commands.

def submit_items(userkey, items, chunksize=64):
    """Submit fingerprints for the items to the Acoustid server.
    """
    data = []  # The running list of dictionaries to submit.
    def submit_chunk():
        """Submit the current accumulated fingerprint data."""
        log.info('submitting {0} fingerprints'.format(len(data)))
        acoustid.submit(API_KEY, userkey, data)
        del data[:]

    for item in items:
        # Get a fingerprint and length for this track.
        if not item.length:
            log.info(u'{0}: no duration available'.format(
                util.displayable_path(item.path)
            ))
            continue
        elif item.acoustid_fingerprint:
            log.info(u'{0}: using existing fingerprint'.format(
                util.displayable_path(item.path)
            ))
            fp = item.acoustid_fingerprint
        else:
            log.info(u'{0}: fingerprinting'.format(
                util.displayable_path(item.path)
            ))
            try:
                _, fp = acoustid.fingerprint_file(item.path)
            except acoustid.FingerprintGenerationError, exc:
                log.info('fingerprint generation failed')
                continue

        # Construct a submission dictionary for this item.
        item_data = {
            'duration': int(item.length),
            'fingerprint': fp,
        }
        if item.mb_trackid:
            item_data['mbid'] = item.mb_trackid
            log.debug('submitting MBID')
        else:
            item_data.update({
                'track': item.title,
                'artist': item.artist,
                'album': item.album,
                'albumartist': item.albumartist,
                'year': item.year,
                'trackno': item.track,
                'discno': item.disc,
            })
            log.debug('submitting textual metadata')
        data.append(item_data)

        # If we have enough data, submit a chunk.
        if len(data) >= chunksize:
            submit_chunk()

    # Submit remaining data in a final chunk.
    submit_chunk()
