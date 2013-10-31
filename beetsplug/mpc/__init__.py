# This file is part of beets.
# Copyright 2013, Peter Schnebel.
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

# requires python-mpd to run. install with:  pip install python-mpd

import logging
# for fetching similar artists, tracks ...
import pylast
# for connecting to mpd
from mpd import MPDClient, CommandError, PendingCommandError
# for catching socket errors
from socket import error as SocketError
# for sockets
from select import select, error
# for time stuff (sleep and unix timestamp)
import time
import os.path

from beets import ui
from beets.util import normpath, plurality
from beets import config
from beets import library
from beets import plugins

log = logging.getLogger('beets')

# for future use
LASTFM = pylast.LastFMNetwork(api_key=plugins.LASTFM_KEY)

# if we lose the connection, how many times do we want to RETRY and how much
# time should we wait between retries
RETRIES = 10
RETRY_INTERVAL = 5

# hookup to the MPDClient internals to get unicode
# see http://www.tarmack.eu/code/mpdunicode.py for the general idea
class MPDClient(MPDClient):
    def _write_command(self, command, args=[]):
        args = [unicode(arg).encode('utf-8') for arg in args]
        super(MPDClient, self)._write_command(command, args)

    def _read_line(self):
        line = super(MPDClient, self)._read_line()
        if line is not None:
            return line.decode('utf-8')
        return None

class Client:
    def __init__(self, library, config):
        self.lib = library
        self.config = config
        self.music_directory = self.config['music_directory'].get()
        self.host = self.config['host'].get()
        self.port = self.config['port'].get()
        self.password = self.config['password'].get()
        self.user = self.config['user'].get()
        self.rating = self.config['rating'].get(bool)
        self.rating_mix = self.config['rating_mix'].get(float)

        self.client = MPDClient()

    def connect(self):
        try:
            self.client.connect(host=self.host, port=self.port)
        except SocketError, e:
            log.error(e)
            exit(1)
        if not self.password == u'':
            try:
                self.client.password(self.password)
            except CommandError, e:
                log.error(e)
                exit(1)

    def disconnect(self):
        self.client.close()
        self.client.disconnect()

    def is_url(self, path):
        """Try to determine if the path is an URL.
        """
        # FIXME:  cover more URL types ...
        if path[:7] == "http://":
            return True
        return False

    def playlist(self):
        """Return the currently active playlist.  Prefixes paths with the
        music_directory, to get the absolute path.
        """
        result = []
        for entry in self._mpdfun('playlistinfo'):
            if not self.is_url(entry['file']):
                result.append(os.path.join(
                    self.music_directory, entry['file']))
            else:
                result.append(entry['file'])
        return result

    def beets_item(self, path):
        """Return the beets item related to path.
        """
        beetsitems = self.lib.items([path])
        if len(beetsitems) == 0:
            return None
        return beetsitems[0]

    def _for_user(self, attribute):
        if self.user != u'':
            return u'{1}[{0}]'.format(self.user, attribute)
        return None

    def _rate(self, play_count, skip_count, rating, skipped):
        if skipped:
            rolling = (rating - rating / 2.0)
        else:
            rolling = (rating + (1.0 - rating) / 2.0)
        stable = (play_count + 1.0) / (play_count + skip_count + 2.0)
        return self.rating_mix * stable \
                + (1.0 - self.rating_mix) * rolling

    def _beets_rate(self, item, skipped):
        """ Update the rating of the beets item.
        """
        if self.rating:
            if not item is None:
                attribute = 'rating'
                item[attribute] = self._rate(
                        item.get('play_count', 0),
                        item.get('skip_count', 0),
                        item.get(attribute, 0.5),
                        skipped)
                log.debug(u'mpc(updated beets): {0} = {1} [{2}]'.format(
                        attribute, item[attribute], item.path))
                user_attribute = self._for_user('rating')
                if not user_attribute is None:
                    item[user_attribute] = self._rate(
                            item.get(self._for_user('play_count'), 0),
                            item.get(self._for_user('skip_count'), 0),
                            item.get(user_attribute, 0.5),
                            skipped)
                    log.debug(u'mpc(updated beets): {0} = {1} [{2}]'.format(
                            user_attribute, item[user_attribute], item.path))
                item.write()
                if item._lib:
                    item.store()


    def _beets_set(self, item, attribute, value=None, increment=None):
        """ Update the beets item.  Set attribute to value or increment the
        value of attribute.  If a user has been given during initialization,
        both the attribute and the attribute with the user prefixed, get
        updated.
        """
        if not item is None:
            changed = False
            if self.user != u'':
                user_attribute = u'{1}[{0}]'.format(self.user, attribute)
            else:
                user_attribute = None
            if not value is None:
                changed = True
                item[attribute] = value
                if not user_attribute is None:
                    item[user_attribute] = value
            if not increment is None:
                changed = True
                item[attribute] = item.get(attribute, 0) + increment
                if not user_attribute is None:
                    item[user_attribute] = item.get(user_attribute, 0) \
                            + increment
            if changed:
                log.debug(u'mpc(updated beets): {0} = {1} [{2}]'.format(
                        attribute, item[attribute], item.path))
                if not user_attribute is None:
                    log.debug(u'mpc(updated beets): {0} = {1} [{2}]'.format(
                            user_attribute, item[user_attribute], item.path))
                item.write()
                if item._lib:
                    item.store()

    def _mpdfun(self, func, **kwargs):
        """Wrapper for requests to the MPD server.  Tries to re-connect if the
        connection was lost ...
        """
        for i in range(RETRIES):
            try:
                if func == 'send_idle':
                    # special case, wait for an event
                    self.client.send_idle()
                    try:
                        select([self.client], [], [])
                    except error:
                        # happens during shutdown and during MPDs library refresh
                        time.sleep(RETRY_INTERVAL)
                        self.connect()
                        continue
                    return self.client.fetch_idle()
                elif func == 'playlistinfo':
                    return self.client.playlistinfo()
                elif func == 'status':
                    return self.client.status()
            except error:
                # happens during shutdown and during MPDs library refresh
                time.sleep(RETRY_INTERVAL)
                self.connect()
                continue
        else:
            # if we excited without breaking, we couldn't reconnect in time :(
            raise Exception(u'failed to re-connect to MPD server')
        return None

    def run(self):
        self.connect()
        self.running = True # exit condition for our main loop
        startup = True # we need to do some special stuff on startup
        now_playing = None # the currently playing song
        current_playlist = None # the currently active playlist
        while self.running:
            if startup:
                # don't wait for an event, read in status and playlist
                changed = ['player', 'playlist']
                startup = False
            else:
                # wait for an event from the MPD server
                changed = self._mpdfun('send_idle')

            if 'player' in changed:
                # the status has changed
                status = self._mpdfun('status')
                if status['state'] == 'stop':
                    log.info(u'mpc(stop)')
                    now_playing = None
                elif status['state'] == 'pause':
                    log.info(u'mpc(pause)')
                    now_playing = None
                elif status['state'] == 'play':
                    current_playlist = self.playlist()
                    song = current_playlist[int(status['song'])]
                    beets_item = self.beets_item(song)
                    if self.is_url(song):
                        # we ignore streams
                        log.info(u'mpc(play|stream): {0}'.format(song))
                    else:
                        log.info(u'mpc(play): {0}'.format(song))
                        # status['time'] = position:duration (in seconds)
                        t = status['time'].split(':')
                        remaining = (int(t[1]) -int(t[0]))

                        if now_playing is not None and now_playing['path'] != song:
                            # song change
                            last_played = now_playing
                            # get the difference of when the song was supposed
                            # to end to now.  if it's smaller then 10 seconds,
                            # we consider if fully played.
                            diff = abs(now_playing['remaining'] -
                                    (time.time() -
                                    now_playing['started']))
                            if diff < 10.0:
                                log.info('mpc(played): {0}'
                                        .format(now_playing))
                                skipped = False
                            else:
                                log.info('mpc(skipped): {0}'
                                        .format(now_playing))
                                skipped = True
                            if skipped:
                                self._beets_set(beets_item,
                                        'skip_count', increment=1)
                            else:
                                self._beets_set(beets_item,
                                        'play_count', increment=1)
                                self._beets_set(beets_item,
                                        'last_played', value=int(time.time()))
                            self._beets_rate(beets_item, skipped)
                        now_playing = {
                                'started'   : time.time(),
                                'remaining' : remaining,
                                'path'      : song,
                        }
                        log.info(u'mpc(now_playing): {0}'
                                .format(now_playing))
                        self._beets_set(beets_item,
                                'last_started', value=int(time.time()))
                else:
                    log.info(u'mpc(status): {0}'.format(status))

            if 'playlist' in changed:
                playlist = self.playlist()
                continue
                for item in playlist:
                    beetsitem = self.beets_item(item)
                    if not beetsitem is None:
                        log.info(u'mpc(playlist|beets): {0}'.format(beetsitem.path))
                    else:
                        log.info(u'mpc(playlist): {0}'.format(item))


class MPCPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(MPCPlugin, self).__init__()
        self.config.add({
            'host': u'127.0.0.1',
            'port': 6600,
            'password': u'',
            'music_directory': u'',
            'user': u'',
            'rating': True,
            'rating_mix': 0.75,
        })

    def commands(self):
        cmd = ui.Subcommand('mpc',
                help='run a MPD client to gather play statistics')
        cmd.parser.add_option('--host', dest='host',
                type='string',
                help='set the hostname of the server to connect to')
        cmd.parser.add_option('--port', dest='port',
                type='int',
                help='set the port of the MPD server to connect to')
        cmd.parser.add_option('--password', dest='password',
                type='string',
                help='set the password of the MPD server to connect to')
        cmd.parser.add_option('--user', dest='user',
                type='string',
                help='set the user for whom we want to gather statistics')

        def func(lib, opts, args):
            self.config.set_args(opts)
            # ATM we need to set the music_directory where the files are
            # located, as the MPD server just tells us the relative paths to
            # the files.  This is good and bad.  'bad' because we have to set
            # an extra option.  'good' because if the MPD server is running on
            # a different host and has mounted the music directory somewhere
            # else, we don't care ...
            Client(lib, self.config).run()

        cmd.func = func
        return [cmd]

# eof
