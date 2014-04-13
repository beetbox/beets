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

"""Updates an MPD index whenever the library is changed.

Put something like the following in your config.yaml to configure:
    mpd:
        host: localhost
        port: 6600
        password: seekrit
"""
from __future__ import print_function

from beets.plugins import BeetsPlugin
import os
import socket
from beets import config

# Global variable so that mpdupdate can detect database changes and run only
# once before beets exits.
database_changed = False


# No need to introduce a dependency on an MPD library for such a
# simple use case. Here's a simple socket abstraction to make things
# easier.
class BufferedSocket(object):
    """Socket abstraction that allows reading by line."""
    def __init__(self, host, port, sep='\n'):
        if host[0] in ['/', '~']:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(os.path.expanduser(host))
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
        self.buf = ''
        self.sep = sep

    def readline(self):
        while self.sep not in self.buf:
            data = self.sock.recv(1024)
            if not data:
                break
            self.buf += data
        if '\n' in self.buf:
            res, self.buf = self.buf.split(self.sep, 1)
            return res + self.sep
        else:
            return ''

    def send(self, data):
        self.sock.send(data)

    def close(self):
        self.sock.close()


def update_mpd(host='localhost', port=6600, password=None):
    """Sends the "update" command to the MPD server indicated,
    possibly authenticating with a password first.
    """
    print('Updating MPD database...')

    s = BufferedSocket(host, port)
    resp = s.readline()
    if 'OK MPD' not in resp:
        print('MPD connection failed:', repr(resp))
        return

    if password:
        s.send('password "%s"\n' % password)
        resp = s.readline()
        if 'OK' not in resp:
            print('Authentication failed:', repr(resp))
            s.send('close\n')
            s.close()
            return

    s.send('update\n')
    resp = s.readline()
    if 'updating_db' not in resp:
        print('Update failed:', repr(resp))

    s.send('close\n')
    s.close()
    print('... updated.')


class MPDUpdatePlugin(BeetsPlugin):
    def __init__(self):
        super(MPDUpdatePlugin, self).__init__()
        config['mpd'].add({
            'host':     u'localhost',
            'port':     6600,
            'password': u'',
        })

        # For backwards compatibility, use any values from the
        # plugin-specific "mpdupdate" section.
        for key in config['mpd'].keys():
            if self.config[key].exists():
                config['mpd'][key] = self.config[key].get()


@MPDUpdatePlugin.listen('database_change')
def handle_change(lib=None):
    global database_changed
    database_changed = True


@MPDUpdatePlugin.listen('cli_exit')
def update(lib=None):
    if database_changed:
        update_mpd(
            config['mpd']['host'].get(unicode),
            config['mpd']['port'].get(int),
            config['mpd']['password'].get(unicode),
        )
