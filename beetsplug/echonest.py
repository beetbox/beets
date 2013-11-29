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

"""Fetch a variety of acoustic metrics from The Echo Nest.
"""
import time
import logging
import socket
import os
import tempfile
from string import Template
import subprocess

from beets import util, config, plugins, ui
import pyechonest
import pyechonest.song
import pyechonest.track

log = logging.getLogger('beets')

# If a request at the EchoNest fails, we want to retry the request RETRIES
# times and wait between retries for RETRY_INTERVAL seconds.
RETRIES = 10
RETRY_INTERVAL = 10

DEVNULL = open(os.devnull, 'wb')
ALLOWED_FORMATS = ('MP3', 'OGG', 'AAC')

# The attributes we can import and where to store them in beets fields.
ATTRIBUTES = {
    'energy':       'energy',
    'liveness':     'liveness',
    'speechiness':  'speechiness',
    'acousticness': 'acousticness',
    'danceability': 'danceability',
    'valence':      'valence',
    'tempo':        'bpm',
}
# We also use echonest_id (song_id) and echonest_fingerprint to speed up
# lookups.
ID_KEY = 'echonest_id'
FINGERPRINT_KEY = 'echonest_fingerprint'

def _splitstrip(string, delim=u','):
    """Split string (at commas by default) and strip whitespace from the
    pieces.
    """
    return [s.strip() for s in string.split(delim)]

class EchonestMetadataPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(EchonestMetadataPlugin, self).__init__()
        self.config.add({
            'auto':    True,
            'apikey':  u'NY2KTZHQ0QDSHBAP6',
            'codegen': None,
            'upload':  True,
            'convert': True,
        })
        self.config.add(ATTRIBUTES)

        pyechonest.config.ECHO_NEST_API_KEY = \
            config['echonest']['apikey'].get(unicode)

        if config['echonest']['codegen']:
            pyechonest.config.CODEGEN_BINARY_OVERRIDE = \
                config['echonest']['codegen'].get(unicode)

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
                    time.sleep(RETRY_INTERVAL)
                elif e.code == 5:
                    # specified identifier does not exist
                    # no use in trying again.
                    log.debug(u'echonest: {}'.format(e))
                    return None
                else:
                    log.error(u'echonest: {0}'.format(e.args[0][0]))
                    return None
            except (pyechonest.util.EchoNestIOError, socket.error) as e:
                log.warn(u'echonest: IO error: {0}'.format(e))
                time.sleep(RETRY_INTERVAL)
            else:
                break
        else:
            # If we exited the loop without breaking, then we used up all
            # our allotted retries.
            raise ui.UserError(u'echonest request failed repeatedly')
            return None
        return result

    def _pick_song(self, songs, item):
        """Helper method to pick the best matching song from a list of songs
        returned by the EchoNest.  Compares artist, title and duration.  If
        the artist and title match and the duration difference is <= 1.0
        seconds, it's considered a match.
        """
        if not songs:
            log.debug(u'echonest: no songs found')
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


    # "Profile" (ID-based) lookup.

    def profile(self, item):
        """Do a lookup on the EchoNest by MusicBrainz ID.
        """
        # Use an existing Echo Nest ID.
        if 'echonest_id' in item:
            enid = item.echonest_id

        # Look up the Echo Nest ID based on the MBID.
        else:
            if not item.mb_trackid:
                log.debug(u'echonest: no ID available')
                return
            mbid = 'musicbrainz:track:{0}'.format(item.mb_trackid)
            track = self._echofun(pyechonest.track.track_from_id,
                                  identifier=mbid)
            if not track:
                log.debug(u'echonest: lookup by MBID failed')
                return
            enid = track.song_id

        # Use the Echo Nest ID to look up the song.
        songs = self._echofun(pyechonest.song.profile, ids=enid,
                buckets=['id:musicbrainz', 'audio_summary'])
        return self._pick_song(songs, item)


    # "Search" (metadata-based) lookup.

    def search(self, item):
        """Search the item at the EchoNest by artist and title.
        """
        songs = self._echofun(pyechonest.song.search, title=item.title,
                              results=100, artist=item.artist,
                              buckets=['id:musicbrainz', 'tracks'])
        return self._pick_song(songs, item)


    # "Identify" (fingerprinting) lookup.

    def fingerprint(self, item):
        """Get the fingerprint for this item from the EchoNest.  If we
        already have a fingerprint, return it and don't calculate it
        again.
        """
        if FINGERPRINT_KEY in item:
            return item[FINGERPRINT_KEY]

        try:
            res = self._echofun(pyechonest.util.codegen,
                                filename=item.path.decode('utf-8'))
        except Exception as e:
            # Frustratingly, the pyechonest library raises a plain Exception
            # when the command is not found.
            log.debug(u'echonest: codegen failed: {0}'.format(e))
            return

        code = res[0]['code']
        log.debug(u'echonest: calculated fingerprint')
        item[FINGERPRINT_KEY] = code
        return code

    def identify(self, item):
        """Try to identify the song at the EchoNest.
        """
        code = self.fingerprint(item)
        if not code:
            return

        songs = self._echofun(pyechonest.song.identify, code=code)
        if not songs:
            log.debug(u'echonest: no songs found for fingerprint')
            return

        return max(songs, key=lambda s: s.score)


    # "Analyze" (upload the audio itself) method.

    def convert(self, item):
        """Converts an item in an unsupported media format to ogg.  Config
        pending.
        This is stolen from Jakob Schnitzers convert plugin.
        """
        fd, dest = tempfile.mkstemp(u'.ogg')
        os.close(fd)
        source = item.path

        log.info(u'echonest: encoding {0} to {1}'.format(
            util.displayable_path(source),
            util.displayable_path(dest),
        ))

        # Build up the FFmpeg command line.
        # FIXME: use avconv?
        command = u'ffmpeg -i $source -y -acodec libvorbis -vn -aq 2 $dest'
        opts = []
        for arg in command.split():
            arg = arg.encode('utf-8')
            opts.append(Template(arg).substitute(source=source, dest=dest))

        # Run the command.
        try:
            subprocess.check_call(opts, close_fds=True, stderr=DEVNULL)
        except (OSError, subprocess.CalledProcessError) as exc:
            log.debug(u'echonest: encode failed: {0}'.format(exc))
            util.remove(dest)
            return

        log.info(u'echonest: finished encoding {0}'.format(
            util.displayable_path(source))
        )
        return dest

    def analyze(self, item):
        """Upload the item to the EchoNest for analysis. May require to
        convert the item to a supported media format.
        """
        # Get the file to upload (either by using the file directly or by
        # transcoding it first).
        source = item.path
        if item.format not in ALLOWED_FORMATS:
            if config['echonest']['convert']:
                source = self.convert(item)
                if not source:
                    log.debug(u'echonest: failed to convert file')
                    return
            else:
                return

        # Upload the audio file.
        log.info(u'echonest: uploading file, please be patient')
        track = self._echofun(pyechonest.track.track_from_filename,
                              filename=source)
        if not track:
            log.debug(u'echonest: failed to upload file')
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
                return pick
        return from_track  # Fall back to track metadata.


    # Shared top-level logic.

    def fetch_song(self, item):
        """Try all methods to get a matching song object from the
        EchoNest. If no method succeeds, return None.
        """
        # There are four different ways to get a song. Each method is a
        # callable that takes the Item as an argument.
        methods = [self.profile, self.search]
        if config['echonest']['codegen']:
            methods.append(self.identify)
        if config['echonest']['upload']:
            methods.append(self.analyze)

        # Try each method in turn.
        for method in methods:
            song = method(item)
            if song:
                if isinstance(song, pyechonest.song.Song):
                    log.debug(u'echonest: got song through {0}: {1} - {2} [{3}]'
                                .format(method.__name__,
                                song.artist_name, song.title,
                                song.audio_summary['duration']))
                else: # it's our dict filled from a track object
                    log.debug(u'echonest: got song through {0}: {1} - {2} [{3}]'
                                .format(method.__name__,
                                item.artist, item.title,
                                song['duration']))
                return song

    def apply_metadata(self, item, song, write=False):
        """Copy the metadata from the EchoNest song to the item.
        """
        # Get either a Song object or a value dictionary.
        if isinstance(song, pyechonest.song.Song):
            log.debug(u'echonest: metadata: echonest_id = {0}'.format(song.id))
            item.echonest_id = song.id
            values = song.audio_summary
        else:
            values = song

        # Update each field.
        for k, v in values.iteritems():
            if k in ATTRIBUTES:
                field = ATTRIBUTES[k]
                log.debug(u'echonest: metadata: {0} = {1}'.format(field, v))
                item[field] = v

        # Write and save.
        if write:
            item.write()
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
        log.info(u'echonest: no update required')
        return False

    def commands(self):
        cmd = ui.Subcommand('echonest',
            help='Fetch metadata from the EchoNest')
        cmd.parser.add_option('-f', '--force', dest='force',
            action='store_true', default=False,
            help='(re-)download information from the EchoNest')

        def func(lib, opts, args):
            self.config.set_args(opts)
            write = config['import']['write'].get(bool)
            for item in lib.items(ui.decargs(args)):
                log.info(u'echonest: {0} - {1} [{2}]'.format(item.artist,
                        item.title, item.length))
                if self.config['force'] or self.requires_update(item):
                    song = self.fetch_song(item)
                    if song:
                        self.apply_metadata(item, song, write)

        cmd.func = func
        return [cmd]


def diff(item1, item2, attributes):
    result = 0.0
    for attr in attributes:
        try:
            result += abs(
                float(item1.get(attr, None)) -
                float(item2.get(attr, None))
            )
        except TypeError:
            result += 1.0
    return result


def similar(lib, src_item, threshold=0.15):
    for item in lib.items():
        if item.path != src_item.path:
            d = diff(item, src_item, ATTRIBUTES.values())
            if d < threshold:
                print(u'{1:2.2f}: {0}'.format(item.path, d))


class EchonestSimilarPlugin(plugins.BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand('echosim', help='show related files')

        def func(lib, opts, args):
            self.config.set_args(opts)
            for item in lib.items(ui.decargs(args)):
                similar(lib, item)

        cmd.func = func
        return [cmd]
