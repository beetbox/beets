# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Fetch a variety of acoustic metrics from The Echo Nest.
"""
from __future__ import division, absolute_import, print_function

import time
import socket
import os
import tempfile
from string import Template
import subprocess

from beets import util, plugins, ui
from beets.dbcore import types
import pyechonest
import pyechonest.song
import pyechonest.track

# If a request at the EchoNest fails, we want to retry the request RETRIES
# times and wait between retries for RETRY_INTERVAL seconds.
RETRIES = 10
RETRY_INTERVAL = 10

DEVNULL = open(os.devnull, 'wb')
ALLOWED_FORMATS = ('MP3', 'OGG', 'AAC')
UPLOAD_MAX_SIZE = 50 * 1024 * 1024

# FIXME: use avconv?
CONVERT_COMMAND = u'ffmpeg -i $source -y -acodec libvorbis -vn -aq 2 $dest'
TRUNCATE_COMMAND = u'ffmpeg -t 300 -i $source'\
                   u'-y -acodec libvorbis -vn -aq 2 $dest'

# Maps attribute names from echonest to their field names in beets.
# The attributes are retrieved from a songs `audio_summary`. See:
# http://echonest.github.io/pyechonest/song.html#pyechonest.song.profile
ATTRIBUTES = {
    'energy':       'energy',
    'liveness':     'liveness',
    'speechiness':  'speechiness',
    'acousticness': 'acousticness',
    'danceability': 'danceability',
    'valence':      'valence',
    'tempo':        'bpm',
}

# Types for the flexible fields added by `ATTRIBUTES`
FIELD_TYPES = {
    'energy':       types.FLOAT,
    'liveness':     types.FLOAT,
    'speechiness':  types.FLOAT,
    'acousticness': types.FLOAT,
    'danceability': types.FLOAT,
    'valence':      types.FLOAT,
}

MUSICAL_SCALE = ['C', 'C#', 'D', 'D#', 'E' 'F',
                 'F#', 'G', 'G#', 'A', 'A#', 'B']


# We also use echonest_id (song_id) and echonest_fingerprint to speed up
# lookups.
ID_KEY = 'echonest_id'
FINGERPRINT_KEY = 'echonest_fingerprint'


def _splitstrip(string, delim=u','):
    """Split string (at commas by default) and strip whitespace from the
    pieces.
    """
    return [s.strip() for s in string.split(delim)]


def diff(item1, item2):
    """Score two Item objects according to the Echo Nest numerical
    fields.
    """
    result = 0.0
    for attr in ATTRIBUTES.values():
        if attr == 'bpm':
            # BPM (tempo) is handled specially to normalize.
            continue

        try:
            result += abs(
                float(item1.get(attr, None)) -
                float(item2.get(attr, None))
            )
        except TypeError:
            result += 1.0

    try:
        bpm1 = float(item1.get('bpm', None))
        bpm2 = float(item2.get('bpm', None))
        result += abs(bpm1 - bpm2) / max(bpm1, bpm2, 1)
    except TypeError:
        result += 1.0

    return result


def similar(lib, src_item, threshold=0.15, fmt='${difference}: ${path}'):
    for item in lib.items():
        if item.path != src_item.path:
            d = diff(item, src_item)
            if d < threshold:
                s = fmt.replace('${difference}', '{:2.2f}'.format(d))
                ui.print_(format(item, s))


class EchonestMetadataPlugin(plugins.BeetsPlugin):

    item_types = FIELD_TYPES

    def __init__(self):
        super(EchonestMetadataPlugin, self).__init__()
        self.config.add({
            'auto':    True,
            'apikey':  u'NY2KTZHQ0QDSHBAP6',
            'upload':  True,
            'convert': True,
            'truncate': True,
        })
        self.config.add(ATTRIBUTES)
        self.config['apikey'].redact = True

        pyechonest.config.ECHO_NEST_API_KEY = \
            self.config['apikey'].get(unicode)

        if self.config['auto']:
            self.import_stages = [self.imported]

    def _echofun(self, func, **kwargs):
        """Wrapper for requests to the EchoNest API.  Will retry up to
        RETRIES times and wait between retries for RETRY_INTERVAL
        seconds.
        """
        for i in range(RETRIES):
            try:
                result = func(**kwargs)
            except pyechonest.util.EchoNestAPIError as e:
                if e.code == 3:
                    # reached access limit per minute
                    self._log.debug(u'rate-limited on try {0}; waiting {1} '
                                    u'seconds', i + 1, RETRY_INTERVAL)
                    time.sleep(RETRY_INTERVAL)
                elif e.code == 5:
                    # specified identifier does not exist
                    # no use in trying again.
                    self._log.debug(u'{0}', e)
                    return None
                else:
                    self._log.error(u'{0}', e.args[0][0])
                    return None
            except (pyechonest.util.EchoNestIOError, socket.error) as e:
                self._log.warn(u'IO error: {0}', e)
                time.sleep(RETRY_INTERVAL)
            except Exception as e:
                # there was an error analyzing the track, status: error
                self._log.debug(u'{0}', e)
                return None
            else:
                break
        else:
            # If we exited the loop without breaking, then we used up all
            # our allotted retries.
            self._log.error(u'request failed repeatedly')
            return None
        return result

    def _pick_song(self, songs, item):
        """Helper method to pick the best matching song from a list of songs
        returned by the EchoNest.  Compares artist, title and duration.  If
        the artist and title match and the duration difference is <= 1.0
        seconds, it's considered a match.
        """
        if not songs:
            self._log.debug(u'no songs found')
            return

        pick = None
        min_dist = item.length
        for song in songs:
            if song.artist_name.lower() == item.artist.lower() \
                    and song.title.lower() == item.title.lower():
                dist = abs(item.length - song.audio_summary['duration'])
                if dist < min_dist:
                    min_dist = dist
                    pick = song
        if min_dist > 2.5:
            return None
        return pick

    def _flatten_song(self, song):
        """Given an Echo Nest song object, return a flat dict containing
        attributes we care about. If song is None, return None.
        """
        if not song:
            return
        values = dict(song.audio_summary)
        values['id'] = song.id
        return values

    # "Profile" (ID-based) lookup.

    def profile(self, item):
        """Do a lookup on the EchoNest by MusicBrainz ID.
        """
        # Use an existing Echo Nest ID.
        if ID_KEY in item:
            enid = item[ID_KEY]

        # Look up the Echo Nest ID based on the MBID.
        else:
            if not item.mb_trackid:
                self._log.debug(u'no ID available')
                return
            mbid = 'musicbrainz:track:{0}'.format(item.mb_trackid)
            track = self._echofun(pyechonest.track.track_from_id,
                                  identifier=mbid)
            if not track:
                self._log.debug(u'lookup by MBID failed')
                return
            enid = track.song_id

        # Use the Echo Nest ID to look up the song.
        songs = self._echofun(pyechonest.song.profile, ids=enid,
                              buckets=['id:musicbrainz', 'audio_summary'])
        return self._flatten_song(self._pick_song(songs, item))

    # "Search" (metadata-based) lookup.

    def search(self, item):
        """Search the item at the EchoNest by artist and title.
        """
        songs = self._echofun(pyechonest.song.search, title=item.title,
                              results=100, artist=item.artist,
                              buckets=['id:musicbrainz', 'tracks',
                                       'audio_summary'])
        return self._flatten_song(self._pick_song(songs, item))

    # "Analyze" (upload the audio itself) method.

    def prepare_upload(self, item):
        """Truncate and convert an item's audio file so it can be
        uploaded to echonest.

        Return a ``(source, tmp)`` tuple where `source` is the path to
        the file to be uploaded and `tmp` is a temporary file to be
        deleted after the upload or `None`.

        If conversion or truncation fails, return `None`.
        """
        source = item.path
        tmp = None
        if item.format not in ALLOWED_FORMATS:
            if self.config['convert']:
                tmp = source = self.convert(source)
            if not tmp:
                return

        if os.stat(source).st_size > UPLOAD_MAX_SIZE:
            if self.config['truncate']:
                source = self.truncate(source)
                if tmp is not None:
                    util.remove(tmp)
                tmp = source
            else:
                return

        if source:
            return source, tmp

    def convert(self, source):
        """Converts an item in an unsupported media format to ogg.  Config
        pending.
        This is stolen from Jakob Schnitzers convert plugin.
        """
        fd, dest = tempfile.mkstemp(b'.ogg')
        os.close(fd)

        self._log.info(u'encoding {0} to {1}',
                       util.displayable_path(source),
                       util.displayable_path(dest))

        opts = []
        for arg in CONVERT_COMMAND.split():
            arg = arg.encode('utf-8')
            opts.append(Template(arg).substitute(source=source, dest=dest))

        # Run the command.
        try:
            util.command_output(opts)
        except (OSError, subprocess.CalledProcessError) as exc:
            self._log.debug(u'encode failed: {0}', exc)
            util.remove(dest)
            return

        self._log.info(u'finished encoding {0}', util.displayable_path(source))
        return dest

    def truncate(self, source):
        """Truncates an item to a size less than UPLOAD_MAX_SIZE."""
        fd, dest = tempfile.mkstemp(u'.ogg')
        os.close(fd)

        self._log.info(u'truncating {0} to {1}',
                       util.displayable_path(source),
                       util.displayable_path(dest))

        opts = []
        for arg in TRUNCATE_COMMAND.split():
            arg = arg.encode('utf-8')
            opts.append(Template(arg).substitute(source=source, dest=dest))

        # Run the command.
        try:
            util.command_output(opts)
        except (OSError, subprocess.CalledProcessError) as exc:
            self._log.debug(u'truncate failed: {0}', exc)
            util.remove(dest)
            return

        self._log.info(u'truncate encoding {0}', util.displayable_path(source))
        return dest

    def analyze(self, item):
        """Upload the item to the EchoNest for analysis. May require to
        convert the item to a supported media format.
        """
        prepared = self.prepare_upload(item)
        if not prepared:
            self._log.debug(u'could not prepare file for upload')
            return

        source, tmp = prepared
        self._log.info(u'uploading file, please be patient')
        track = self._echofun(pyechonest.track.track_from_filename,
                              filename=source)
        if tmp is not None:
            util.remove(tmp)

        if not track:
            self._log.debug(u'failed to upload file')
            return

        # Sometimes we have a track but no song. I guess this happens for
        # new / unverified songs. We need to "extract" the audio_summary
        # from the track object manually.  I don't know why the
        # pyechonest API handles tracks (merge audio_summary to __dict__)
        # and songs (keep audio_summary in an extra attribute)
        # differently.
        # Maybe a patch for pyechonest could help?

        # First get the (limited) metadata from the track in case
        # there's no associated song.
        from_track = {}
        for key in ATTRIBUTES:
            try:
                from_track[key] = getattr(track, key)
            except AttributeError:
                pass
        from_track['duration'] = track.duration

        # Try to look up a song for the full metadata.
        try:
            song_id = track.song_id
        except AttributeError:
            return from_track
        songs = self._echofun(pyechonest.song.profile,
                              ids=[song_id], track_ids=[track.id],
                              buckets=['audio_summary'])
        if songs:
            pick = self._pick_song(songs, item)
            if pick:
                return self._flatten_song(pick)
        return from_track  # Fall back to track metadata.

    # Shared top-level logic.

    def fetch_song(self, item):
        """Try all methods to get a matching song object from the
        EchoNest. If no method succeeds, return None.
        """
        # There are four different ways to get a song. Each method is a
        # callable that takes the Item as an argument.
        methods = [self.profile, self.search]
        if self.config['upload']:
            methods.append(self.analyze)

        # Try each method in turn.
        for method in methods:
            song = method(item)
            if song:
                self._log.debug(u'got song through {0}: {1} [{2}]',
                                method.__name__,
                                item,
                                song.get('duration'),
                                )
                return song

    def apply_metadata(self, item, values, write=False):
        """Copy the metadata from the dictionary of song information to
        the item.
        """
        # Update each field.
        for k, v in values.iteritems():
            if k in ATTRIBUTES:
                field = ATTRIBUTES[k]
                self._log.debug(u'metadata: {0} = {1}', field, v)
                if field == 'bpm':
                    item[field] = int(v)
                else:
                    item[field] = v
        if 'key' in values and 'mode' in values:
            key = MUSICAL_SCALE[values['key'] - 1]
            if values['mode'] == 0:  # Minor key
                key += 'm'
            item['initial_key'] = key
        if 'id' in values:
            enid = values['id']
            self._log.debug(u'metadata: {0} = {1}', ID_KEY, enid)
            item[ID_KEY] = enid

        # Write and save.
        if write:
            item.try_write()
        item.store()

    # Automatic (on-import) metadata fetching.

    def imported(self, session, task):
        """Import pipeline stage.
        """
        for item in task.imported_items():
            song = self.fetch_song(item)
            if song:
                self.apply_metadata(item, song)

    # Explicit command invocation.

    def requires_update(self, item):
        """Check if this item requires an update from the EchoNest (its
        data is missing).
        """
        for field in ATTRIBUTES.values():
            if not item.get(field):
                return True
        self._log.info(u'no update required')
        return False

    def commands(self):
        fetch_cmd = ui.Subcommand('echonest',
                                  help=u'fetch metadata from The Echo Nest')
        fetch_cmd.parser.add_option(
            u'-f', u'--force', dest='force',
            action='store_true', default=False,
            help=u'(re-)download information from the EchoNest'
        )

        def fetch_func(lib, opts, args):
            self.config.set_args(opts)
            write = ui.should_write()
            for item in lib.items(ui.decargs(args)):
                self._log.info(u'{0}', item)
                if self.config['force'] or self.requires_update(item):
                    song = self.fetch_song(item)
                    if song:
                        self.apply_metadata(item, song, write)

        fetch_cmd.func = fetch_func

        sim_cmd = ui.Subcommand('echosim', help=u'show related files')
        sim_cmd.parser.add_option(
            u'-t', u'--threshold', dest='threshold', action='store',
            type='float', default=0.15, help=u'Set difference threshold'
        )
        sim_cmd.parser.add_format_option()

        def sim_func(lib, opts, args):
            self.config.set_args(opts)
            for item in lib.items(ui.decargs(args)):
                similar(lib, item, opts.threshold, opts.format)

        sim_cmd.func = sim_func

        return [fetch_cmd, sim_cmd]
