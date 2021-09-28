# This file is part of beets.
# Copyright 2016, Peter Schnebel and Johann Klähn.
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


import mpd
import time
import os

from beets import ui
from beets import config
from beets import plugins
from beets import library
from beets.util import displayable_path
from beets.dbcore import types

# If we lose the connection, how many times do we want to retry and how
# much time should we wait between retries?
RETRIES = 10
RETRY_INTERVAL = 5


mpd_config = config['mpd']


def is_url(path):
    """Try to determine if the path is an URL.
    """
    if isinstance(path, bytes):  # if it's bytes, then it's a path
        return False
    return path.split('://', 1)[0] in ['http', 'https']


class MPDClientWrapper:
    def __init__(self, log):
        self._log = log

        self.music_directory = mpd_config['music_directory'].as_str()
        self.strip_path = mpd_config['strip_path'].as_str()

        # Ensure strip_path end with '/'
        if not self.strip_path.endswith('/'):
            self.strip_path += '/'

        self._log.debug('music_directory: {0}', self.music_directory)
        self._log.debug('strip_path: {0}', self.strip_path)

        self.client = mpd.MPDClient()

    def connect(self):
        """Connect to the MPD.
        """
        host = mpd_config['host'].as_str()
        port = mpd_config['port'].get(int)

        if host[0] in ['/', '~']:
            host = os.path.expanduser(host)

        self._log.info('connecting to {0}:{1}', host, port)
        try:
            self.client.connect(host, port)
        except OSError as e:
            raise ui.UserError(f'could not connect to MPD: {e}')

        password = mpd_config['password'].as_str()
        if password:
            try:
                self.client.password(password)
            except mpd.CommandError as e:
                raise ui.UserError(
                    f'could not authenticate to MPD: {e}'
                )

    def disconnect(self):
        """Disconnect from the MPD.
        """
        self.client.close()
        self.client.disconnect()

    def get(self, command, retries=RETRIES):
        """Wrapper for requests to the MPD server. Tries to re-connect if the
        connection was lost (f.ex. during MPD's library refresh).
        """
        try:
            return getattr(self.client, command)()
        except (OSError, mpd.ConnectionError) as err:
            self._log.error('{0}', err)

        if retries <= 0:
            # if we exited without breaking, we couldn't reconnect in time :(
            raise ui.UserError('communication with MPD server failed')

        time.sleep(RETRY_INTERVAL)

        try:
            self.disconnect()
        except mpd.ConnectionError:
            pass

        self.connect()
        return self.get(command, retries=retries - 1)

    def currentsong(self):
        """Return the path to the currently playing song, along with its
        songid.  Prefixes paths with the music_directory, to get the absolute
        path.
        In some cases, we need to remove the local path from MPD server,
        we replace 'strip_path' with ''.
        `strip_path` defaults to ''.
        """
        result = None
        entry = self.get('currentsong')
        if 'file' in entry:
            if not is_url(entry['file']):
                file = entry['file']
                if file.startswith(self.strip_path):
                    file = file[len(self.strip_path):]
                result = os.path.join(self.music_directory, file)
            else:
                result = entry['file']
        self._log.debug('returning: {0}', result)
        return result, entry.get('id')

    def status(self):
        """Return the current status of the MPD.
        """
        return self.get('status')

    def events(self):
        """Return list of events. This may block a long time while waiting for
        an answer from MPD.
        """
        return self.get('idle')


class MPDStats:
    def __init__(self, lib, log):
        self.lib = lib
        self._log = log

        self.do_rating = mpd_config['rating'].get(bool)
        self.rating_mix = mpd_config['rating_mix'].get(float)
        self.time_threshold = 10.0  # TODO: maybe add config option?

        self.now_playing = None
        self.mpd = MPDClientWrapper(log)

    def rating(self, play_count, skip_count, rating, skipped):
        """Calculate a new rating for a song based on play count, skip count,
        old rating and the fact if it was skipped or not.
        """
        if skipped:
            rolling = (rating - rating / 2.0)
        else:
            rolling = (rating + (1.0 - rating) / 2.0)
        stable = (play_count + 1.0) / (play_count + skip_count + 2.0)
        return (self.rating_mix * stable +
                (1.0 - self.rating_mix) * rolling)

    def get_item(self, path):
        """Return the beets item related to path.
        """
        query = library.PathQuery('path', path)
        item = self.lib.items(query).get()
        if item:
            return item
        else:
            self._log.info('item not found: {0}', displayable_path(path))

    def update_item(self, item, attribute, value=None, increment=None):
        """Update the beets item. Set attribute to value or increment the value
        of attribute. If the increment argument is used the value is cast to
        the corresponding type.
        """
        if item is None:
            return

        if increment is not None:
            item.load()
            value = type(increment)(item.get(attribute, 0)) + increment

        if value is not None:
            item[attribute] = value
            item.store()

            self._log.debug('updated: {0} = {1} [{2}]',
                            attribute,
                            item[attribute],
                            displayable_path(item.path))

    def update_rating(self, item, skipped):
        """Update the rating for a beets item. The `item` can either be a
        beets `Item` or None. If the item is None, nothing changes.
        """
        if item is None:
            return

        item.load()
        rating = self.rating(
            int(item.get('play_count', 0)),
            int(item.get('skip_count', 0)),
            float(item.get('rating', 0.5)),
            skipped)

        self.update_item(item, 'rating', rating)

    def handle_song_change(self, song):
        """Determine if a song was skipped or not and update its attributes.
        To this end the difference between the song's supposed end time
        and the current time is calculated. If it's greater than a threshold,
        the song is considered skipped.

        Returns whether the change was manual (skipped previous song or not)
        """
        diff = abs(song['remaining'] - (time.time() - song['started']))

        skipped = diff >= self.time_threshold

        if skipped:
            self.handle_skipped(song)
        else:
            self.handle_played(song)

        if self.do_rating:
            self.update_rating(song['beets_item'], skipped)

        return skipped

    def handle_played(self, song):
        """Updates the play count of a song.
        """
        self.update_item(song['beets_item'], 'play_count', increment=1)
        self._log.info('played {0}', displayable_path(song['path']))

    def handle_skipped(self, song):
        """Updates the skip count of a song.
        """
        self.update_item(song['beets_item'], 'skip_count', increment=1)
        self._log.info('skipped {0}', displayable_path(song['path']))

    def on_stop(self, status):
        self._log.info('stop')

        # if the current song stays the same it means that we stopped on the
        # current track and should not record a skip.
        if self.now_playing and self.now_playing['id'] != status.get('songid'):
            self.handle_song_change(self.now_playing)

        self.now_playing = None

    def on_pause(self, status):
        self._log.info('pause')
        self.now_playing = None

    def on_play(self, status):

        path, songid = self.mpd.currentsong()

        if not path:
            return

        played, duration = map(int, status['time'].split(':', 1))
        remaining = duration - played

        if self.now_playing:
            if self.now_playing['path'] != path:
                self.handle_song_change(self.now_playing)
            else:
                # In case we got mpd play event with same song playing
                # multiple times,
                # assume low diff means redundant second play event
                # after natural song start.
                diff = abs(time.time() - self.now_playing['started'])

                if diff <= self.time_threshold:
                    return

                if self.now_playing['path'] == path and played == 0:
                    self.handle_song_change(self.now_playing)

        if is_url(path):
            self._log.info('playing stream {0}', displayable_path(path))
            self.now_playing = None
            return

        self._log.info('playing {0}', displayable_path(path))

        self.now_playing = {
            'started': time.time(),
            'remaining': remaining,
            'path': path,
            'id': songid,
            'beets_item': self.get_item(path),
        }

        self.update_item(self.now_playing['beets_item'],
                         'last_played', value=int(time.time()))

    def run(self):
        self.mpd.connect()
        events = ['player']

        while True:
            if 'player' in events:
                status = self.mpd.status()

                handler = getattr(self, 'on_' + status['state'], None)

                if handler:
                    handler(status)
                else:
                    self._log.debug('unhandled status "{0}"', status)

            events = self.mpd.events()


class MPDStatsPlugin(plugins.BeetsPlugin):

    item_types = {
        'play_count': types.INTEGER,
        'skip_count': types.INTEGER,
        'last_played': library.DateType(),
        'rating': types.FLOAT,
    }

    def __init__(self):
        super().__init__()
        mpd_config.add({
            'music_directory': config['directory'].as_filename(),
            'strip_path': '',
            'rating': True,
            'rating_mix': 0.75,
            'host': os.environ.get('MPD_HOST', 'localhost'),
            'port': int(os.environ.get('MPD_PORT', 6600)),
            'password': '',
        })
        mpd_config['password'].redact = True

    def commands(self):
        cmd = ui.Subcommand(
            'mpdstats',
            help='run a MPD client to gather play statistics')
        cmd.parser.add_option(
            '--host', dest='host', type='string',
            help='set the hostname of the server to connect to')
        cmd.parser.add_option(
            '--port', dest='port', type='int',
            help='set the port of the MPD server to connect to')
        cmd.parser.add_option(
            '--password', dest='password', type='string',
            help='set the password of the MPD server to connect to')

        def func(lib, opts, args):
            mpd_config.set_args(opts)

            # Overrides for MPD settings.
            if opts.host:
                mpd_config['host'] = opts.host.decode('utf-8')
            if opts.port:
                mpd_config['host'] = int(opts.port)
            if opts.password:
                mpd_config['password'] = opts.password.decode('utf-8')

            try:
                MPDStats(lib, self._log).run()
            except KeyboardInterrupt:
                pass

        cmd.func = func
        return [cmd]
