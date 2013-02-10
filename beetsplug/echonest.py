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
the autotagger. Requires the pyechonest library and an echonest
codegen binary.
"""
import logging
import collections

from beets import ui, util, config, plugins, mediafile
from beets.util import confit
from beets.autotag import hooks

import pyechonest.song
import pyechonest.config
import pyechonest.util

TRACK_ID_WEIGHT = 10.0

log = logging.getLogger('beets')

# Stores the Echonest match information for each track. This is
# populated when an import task begins and then used when searching
# for candidates. It maps audio file paths to (recording_ids,
# release_ids) pairs. If a given path is not present in the mapping,
# then no match was found.
_matches = {}

# Stores the fingerprint and echonest IDs and audio summaries for each
# track. This is stored as metadata for each track for later use but
# is not relevant for autotagging. Currrently this data is stored in
# the database itself, not as MediaFile fields.
_fingerprints = {}
_echonestids = {}
_echonestsummaries = {}
_echonestfields = {'danceability':float,
                   'duration':float,
                   'energy':float,
                   'key':int,
                   'liveness':float,
                   'loudness':float,
                   'mode':int,
                   'speechiness':float,
                   'tempo':float,
                   'time_signature':int}


def _echonest_match(path):
    """Gets metadata for a file from Echonest and populates the
    _matches, _fingerprints, _echonestids, and _echonestsummaries
    dictionaries accordingly.
    """
    try:
        pyechonest.config.ECHO_NEST_API_KEY = config['echonest']['apikey'].get(unicode)
    except confit.NotFoundError:
        raise ui.UserError('echonest: no Echonest user API key provided')

    try:
        pyechonest.config.CODEGEN_BINARY_OVERRIDE = config['echonest']['codegen'].get(unicode)
    except confit.NotFoundError:
        pass

    try:
        query = pyechonest.util.codegen(path.decode('utf-8'))
        songs = pyechonest.song.identify(query_obj=query[0],
                                         buckets=['id:musicbrainz', 'tracks'])
    except Exception as exc:
        log.error('echonest: fingerprinting of {0} failed: {1}'
                  .format(util.syspath(path),
                          str(exc)))
        return None

    # The echonest codegen binaries always return a list, even for a
    # single file. Since we're only dealing with single files here, it
    # is safe to just grab the one element of said list
    _fingerprints[path] = query[0]['code']

    log.debug('echonest: fingerprinted {0}'
              .format(util.syspath(path)))

    # no matches reported by the song/identify api call
    if not songs:
        return None

    # song/identify may return multiple songs, each with multiple
    # tracks. this grabs the best song match according to the score
    result = max(songs, key=lambda s: s.score)
    _echonestids[path] = result.id

    del result.audio_summary['analysis_url']
    del result.audio_summary['audio_md5']
    _echonestsummaries[path] = result.audio_summary

    # Get recording and releases from the result.
    recordings = result.get_tracks('musicbrainz')
    if not recordings:
        return None

    recording_ids = []
    release_ids = []

    # filter out those for which echonest holds no mbid
    for recording in recordings:
        if 'foreign_id' in recording:
            mbid = recording['foreign_id'].split(':')[-1]
            recording_ids.append(mbid)
        if 'foreign_release_id' in recording:
            mbid = recording['foreign_release_id'].split(':')[-1]
            release_ids.append(mbid)

    def _format(ids):
        return ",".join(map(lambda x: '{0}..{1}'.format(x[:4], x[-4:]),
                            ids))

    if recording_ids:
        log.debug('echonest: matched {0} recordings: {1}'.format(len(recording_ids),
                                                                 _format(recording_ids)))
    if release_ids:
        log.debug('echonest: matched {0} releases: {1}'.format(len(release_ids),
                                                               _format(release_ids)))

    _matches[path] = recording_ids, release_ids

# Plugin structure and autotagging logic.

def _all_releases(items):
    """Given an iterable of Items, determines (according to Echonest)
    which releases the items have in common. Generates release IDs.
    """

    # Count the number of "hits" for each release.
    relcounts = collections.defaultdict(int)
    for item in items:
        if item.path not in _matches:
            continue

        _, release_ids = _matches[item.path]
        for release_id in release_ids:
            relcounts[release_id] += 1

    for release_id, count in sorted(relcounts.iteritems(), key=lambda x: x[1]):
        log.debug('echonest: examining release id {0} ({1}/{2})'
                  .format(release_id, count, len(items)))
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

    def item_fields(self):
        def _format(field, fn=str.capitalize, sep=' '):
            return sep.join(map(fn, field.split('_')))

        descriptors = {}
        if not config['echonest']['write'].get(bool):
            return descriptors

        for field, out_type in _echonestfields.iteritems():
            mp3 = mediafile.StorageStyle('TXXX', id3_desc='Echonest ' + _format(field))
            mp4 = mediafile.StorageStyle("----:com.apple.iTunes:Echonest {0}".format(_format(field)))
            etc = mediafile.StorageStyle('ECHONEST_' + _format(field, str.upper, '_'))
            asf = mediafile.StorageStyle('Echonest/' + _format(field))
            media_field = mediafile.MediaField(out_type=out_type,
                                               mp3=mp3,
                                               mp4=mp4,
                                               asf=asf,
                                               etc=etc)
            descriptors['echonest_' + field] = media_field

        return descriptors


# Hooks into import process.
@EchonestPlugin.listen('import_task_start')
def fingerprint_task(task, session):
    """Fingerprint each item in the task for later use during the
    autotagging candidate search.
    """
    items = task.items if task.is_album else [task.item]
    for item in items:
        _echonest_match(item.path)

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
            for f in _echonestfields.keys():
                setattr(item, 'echonest_' + f, _echonestsummaries[item.path][f])



# Additional path fields. Since there's a bunch of them defined in
# _echonestfields, we define these dynamically
def _make_templ_function(field):
    """Build a function definition string ready for evaluation as
    @template_field expects it"""
    return """\
@EchonestPlugin.template_field('{f}')
def _tmpl_{f}(item):
    v = getattr(item, '{f}')
    if isinstance(v, float):
        v = u'%.2f' % getattr(item, '{f}')
    return v
""".format(f='echonest_' + field)

for f in _echonestfields.keys():
    exec _make_templ_function(f)
