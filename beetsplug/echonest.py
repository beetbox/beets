# This file is not part of beets.
# Copyright 2013, Pedro Silva.
#
# Based on beetsplug/chroma.py
# (Copyright 2013, Adrian Sampson)
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Adds Echoprint/ENMFP Echonest acoustic fingerprinting support to
the autotagger. Requires the pyechonest library.
codegen binary.
"""
import logging
import collections

from beets import ui, util, config, plugins
from beets.util import confit
from beets.autotag import hooks

import pyechonest.song
import pyechonest.config
import pyechonest.util

API_KEY = 'O8IIFBUUBEO55GEHU'
TRACK_ID_WEIGHT = 10.0
COMMON_REL_THRESH = 0.6  # How many tracks must have an album in common?

log = logging.getLogger('beets')

# Stores the Echonest match information for each track. This is
# populated when an import task begins and then used when searching
# for candidates. It maps audio file paths to (recording_ids,
# release_ids) pairs. If a given path is not present in the mapping,
# then no match was found.
_matches = {}

# Stores the fingerprint and echonest IDs and audio summaries for each
# track. This is stored as metadata for each track for later use but
# is not relevant for autotagging.
_fingerprints = {}
_echonestids = {}
_echonestsummaries = {}
_echonestfields = ['danceability', 'duration', 'energy', 'key', 'liveness',
                   'loudness', 'mode', 'speechiness', 'tempo', 'time_signature',
                   'song_type']

def echonest_match(path):
    """Gets metadata for a file from Echonest and populates the
    _matches, _fingerprints, and _echonestids dictionaries
    accordingly.
    """
    try:
        pyechonest.config.ECHO_NEST_API_KEY = beets.config['echonest']['apikey'].get(unicode)
    except confit.NotFoundError:
        raise ui.UserError('no Echonest user API key provided')

    try:
        pyechonest.config.CODEGEN_BINARY_OVERRIDE = beets.config['echonest']['codegen'].get(unicode)
    except:
        pass

    try:
        query = pyechonest.util.codegen(util.syspath(path).decode('utf-8'))
        songs = pyechonest.song.identify(query_obj=query[0],
                                         buckets=['id:musicbrainz', 'tracks'])
    except Exception as exc:
        log.error('echonest: fingerprinting of {0} failed: {1}'.format(repr(path), str(exc)))
        return None

    _fingerprints[path] = query[0]['code']

    log.debug('echonest: fingerprinted {0}'.format(repr(path)).encode('utf-8'))
    log.debug('echonest: {0} song matches found'.format(len(songs)))
    if not songs:
        return None

    result = max(songs, key=lambda s: s.score)  # Best match.
    _echonestids[path] = result.id

    try:
        get_summary = beets.config['echonest']['summary'].get(bool)
    except confit.NotFoundError:
        get_summary = False

    if get_summary:
        del result.audio_summary['analysis_url']
        del result.audio_summary['audio_md5']
        result.audio_summary.update(result.song_type)
        _echonestsummaries[path] = result.audio_summary

    # Get recording and releases from the result.
    recordings = result.get_tracks('musicbrainz')

    log.debug('echonest: {0} track matches found'.format(len(recordings)))
    if not recordings:
        return None

    recording_ids = []
    release_ids = []

    for recording in recordings:
        if 'foreign_id' in recording:
            mbid = recording['foreign_id'].split(':')[-1]
            recording_ids.append(mbid)
        if 'foreign_release_id' in recording:
            mbid = recording['foreign_release_id'].split(':')[-1]
            release_ids.append(mbid)

    log.debug('echonest: matched recordings {0}'.format(recording_ids))
    _matches[path] = recording_ids, release_ids

# Plugin structure and autotagging logic.

def _all_releases(items):
    """Given an iterable of Items, determines (according to Echonest)
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
        coeff = float(count) / len(items)
        log.debug('echonest: examining release id {0} with frequency {1} (coefficient: {2})'.format(release_id, count, coeff))
        if coeff > COMMON_REL_THRESH:
            log.debug('echonest: chosen release id {0}'.format(release_id))
            yield release_id


class EchonestPlugin(plugins.BeetsPlugin):
    def track_distance(self, item, info):
        if item.path not in _matches:
            # Match failed.
            return 0.0, 0.0

        recording_ids, _ = _matches[item.path]
        if info.track_id in recording_ids:
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
        log.debug('echonest: album candidates: {0}'.format(len(albums)))
        return albums

    def item_candidates(self, item):
        if item.path not in _matches:
            return []

        recording_ids, _ = _matches[item.path]
        tracks = []
        for recording_id in recording_ids:
            track = hooks._track_for_id(recording_id)
            if track:
                tracks.append(track)
        log.debug('echonest: item candidates: {0}'.format(len(tracks)))
        return tracks


# Hooks into import process.

@EchonestPlugin.listen('import_task_start')
def fingerprint_task(task, session):
    """Fingerprint each item in the task for later use during the
    autotagging candidate search.
    """
    items = task.items if task.is_album else [task.item]
    for item in items:
        echonest_match(item.path)

@EchonestPlugin.listen('import_task_apply')
def apply_echonest_metadata(task, session):
    """Apply Echonest metadata (fingerprint and ID) to the task's items.
    """
    for item in task.imported_items():
        if item.path in _fingerprints:
            item.echonest_fingerprint = _fingerprints[item.path]
        if item.path in _echonestids:
            item.echonest_id = _echonestids[item.path]
        if item.path in _echonestsummaries:
            for f in _echonestfields:
                setattr(item, f, _echonestsummaries[item.path][f])

# Additional path fields

def _make_templ_function(field):
    return """\
@EchonestPlugin.template_field('{f}')
def _tmpl_{f}(item):
    v = getattr(item, '{f}')
    if isinstance(v, float):
        v = u'%.2f' % getattr(item, '{f}')
    return v
""".format(f=field)

try:
    get_summary = beets.config['echonest']['summary'].get(bool)
except confit.NotFoundError:
    get_summary = False

if get_summary:
    for f in _echonestfields:
        exec _make_templ_function(f)
