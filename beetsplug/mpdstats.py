# coding=utf-8
# This file is part of beets.
# Copyright 2013, Peter Schnebel and Johann Klähn.
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

import logging
import mpd
import socket
import select
import time
import os

from beets import ui
from beets import config
from beets import plugins
from beets import library
from beets.util import displayable_path

log = logging.getLogger('beets')

# If we lose the connection, how many times do we want to retry and how
# much time should we wait between retries?
RETRIES = 10
RETRY_INTERVAL = 5


def is_url(path):
    """Try to determine if the path is an URL.
    """
    return path.split('://', 1)[0] in ['http', 'https']


# Use the MPDClient internals to get unicode.
# see http://www.tarmack.eu/code/mpdunicode.py for the general idea
class MPDClient(mpd.MPDClient):
    def _write_command(self, command, args=[]):
        args = [unicode(arg).encode('utf-8') for arg in args]
        super(MPDClient, self)._write_command(command, args)

    def _read_line(self):
        line = super(MPDClient, self)._read_line()
        if line is not None:
            return line.decode('utf-8')
        return None


class MPDClientWrapper(object):
    def __init__(self):
        self.music_directory = (
            config['mpdstats']['music_directory'].get(unicode))

        self.client = MPDClient()

    def connect(self):
        """Connect to the MPD.
        """
        host = config['mpd']['host'].get(unicode)
        port = config['mpd']['port'].get(int)

        if host[0] in ['/', '~']:
            host = os.path.expanduser(host)

        log.info(u'mpdstats: connecting to {0}:{1}'.format(host, port))
        try:
            self.client.connect(host, port)
        except socket.error as e:
            raise ui.UserError('could not connect to MPD: {0}'.format(e))

        password = config['mpd']['password'].get(unicode)
        if password:
            try:
                self.client.password(password)
            except mpd.CommandError as e:
                raise ui.UserError(
                    'could not authenticate to MPD: {0}'.format(e)
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
        except (select.error, mpd.ConnectionError) as err:
            log.error(u'mpdstats: {0}'.format(err))

        if retries <= 0:
            # if we exited without breaking, we couldn't reconnect in time :(
            raise ui.UserError(u'communication with MPD server failed')

        time.sleep(RETRY_INTERVAL)

        try:
            self.disconnect()
        except mpd.ConnectionError:
            pass

        self.connect()
        return self.get(command, retries=retries - 1)

    def playlist(self):
        """Return the currently active playlist.  Prefixes paths with the
        music_directory, to get the absolute path.
        """
        result = {}
        for entry in self.get('playlistinfo'):
            if not is_url(entry['file']):
                result[entry['id']] = os.path.join(
                    self.music_directory, entry['file'])
            else:
                result[entry['id']] = entry['file']
        return result

    def status(self):
        """Return the current status of the MPD.
        """
        return self.get('status')

    def events(self):
        """Return list of events. This may block a long time while waiting for
        an answer from MPD.
        """
        return self.get('idle')


class MPDStats(object):
    def __init__(self, lib):
        self.lib = lib

        self.do_rating = config['mpdstats']['rating'].get(bool)
        self.rating_mix = config['mpdstats']['rating_mix'].get(float)
        self.time_threshold = 10.0  # TODO: maybe add config option?

        self.now_playing = None
        self.mpd = MPDClientWrapper()

    def rating(self, play_count, skip_count, rating, skipped):
        """Calculate a new rating for a song based on play count, skip count,
        old rating and the fact if it was skipped or not.
        """
        if skipped:
            rolling = (rating - rating / 2.0)
        else:
            rolling = (rating + (1.0 - rating) / 2.0)
        stable = (play_count + 1.0) / (play_count + skip_count + 2.0)
        return (self.rating_mix * stable
                + (1.0 - self.rating_mix) * rolling)

    def get_item(self, path):
        """Return the beets item related to path.
        """
        query = library.PathQuery('path', path)
        item = self.lib.items(query).get()
        if item:
            return item
        else:
            log.info(u'mpdstats: item not found: {0}'.format(
                displayable_path(path)
            ))

    @staticmethod
    def update_item(item, attribute, value=None, increment=None):
        """Update the beets item. Set attribute to value or increment the value
        of attribute. If the increment argument is used the value is cast to the
        corresponding type.
        """
        if item is None:
            return

        if increment is not None:
            item.load()
            value = type(increment)(item.get(attribute, 0)) + increment

        if value is not None:
            item[attribute] = value
            item.store()

            log.debug(u'mpdstats: updated: {0} = {1} [{2}]'.format(
                attribute,
                item[attribute],
                displayable_path(item.path),
            ))

    def update_rating(self, item, skipped):
        """Update the rating for a beets item.
        """
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
        """
        diff = abs(song['remaining'] - (time.time() - song['started']))

        skipped = diff >= self.time_threshold

        if skipped:
            self.handle_skipped(song)
        else:
            self.handle_played(song)

        if self.do_rating:
            self.update_rating(song['beets_item'], skipped)

    def handle_played(self, song):
        """Updates the play count of a song.
        """
        self.update_item(song['beets_item'], 'play_count', increment=1)
        log.info(u'mpdstats: played {0}'.format(
            displayable_path(song['path'])
        ))

    def handle_skipped(self, song):
        """Updates the skip count of a song.
        """
        self.update_item(song['beets_item'], 'skip_count', increment=1)
        log.info(u'mpdstats: skipped {0}'.format(
            displayable_path(song['path'])
        ))

    def on_stop(self, status):
        log.info(u'mpdstats: stop')
        self.now_playing = None

    def on_pause(self, status):
        log.info(u'mpdstats: pause')
        self.now_playing = None

    def on_play(self, status):
        playlist = self.mpd.playlist()
        path = playlist.get(status['songid'])

        if not path:
            return

        if is_url(path):
            log.info(u'mpdstats: playing stream {0}'.format(
                displayable_path(path)
            ))
            return

        played, duration = map(int, status['time'].split(':', 1))
        remaining = duration - played

        if self.now_playing and self.now_playing['path'] != path:
            self.handle_song_change(self.now_playing)

        log.info(u'mpdstats: playing {0}'.format(
            displayable_path(path)
        ))

        self.now_playing = {
            'started':    time.time(),
            'remaining':  remaining,
            'path':       path,
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
                    log.debug(u'mpdstats: unhandled status "{0}"'.format(status))

            events = self.mpd.events()


class MPDStatsPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(MPDStatsPlugin, self).__init__()
        self.config.add({
            'music_directory': config['directory'].as_filename(),
            'rating':          True,
            'rating_mix':      0.75,
        })
        config['mpd'].add({
            'host':            u'localhost',
            'port':            6600,
            'password':        u'',
        })

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
            self.config.set_args(opts)

            # Overrides for MPD settings.
            if opts.host:
                config['mpd']['host'] = opts.host.decode('utf8')
            if opts.port:
                config['mpd']['host'] = int(opts.port)
            if opts.password:
                config['mpd']['password'] = opts.password.decode('utf8')

            try:
                MPDStats(lib).run()
            except KeyboardInterrupt:
                pass

        cmd.func = func
        return [cmd]
