# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

Put something like the following in your .beetsconfig to configure:
    [mpdupdate]
    host = localhost
    port = 6600
    password = seekrit
"""

from beets.plugins import BeetsPlugin
from beets import ui
import socket

# No need to introduce a dependency on an MPD library for such a
# simple use case. Here's a simple socket abstraction to make things
# easier.
class BufferedSocket(object):
    """Socket abstraction that allows reading by line."""
    def __init__(self, sep='\n'):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.buf = ''
        self.sep = sep

    def connect(self, host, port):
        self.sock.connect((host, port))

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
    print 'Updating MPD database...'

    s = BufferedSocket()
    s.connect(host, port)
    resp = s.readline()
    if 'OK MPD' not in resp:
        print 'MPD connection failed:', repr(resp)
        return
    
    if password:
        s.send('password "%s"\n' % password)
        resp = s.readline()
        if 'OK' not in resp:
            print 'Authentication failed:', repr(resp)
            s.send('close\n')
            s.close()
            return

    s.send('update\n')
    resp = s.readline()
    if 'updating_db' not in resp:
        print 'Update failed:', repr(resp)

    s.send('close\n')
    s.close()
    print '... updated.'

options = {
    'host': 'localhost',
    'port': 6600,
    'password': None,
}
class MPDUpdatePlugin(BeetsPlugin):
    def configure(self, config):
        options['host'] = \
            ui.config_val(config, 'mpdupdate', 'host', 'localhost')
        options['port'] = \
            int(ui.config_val(config, 'mpdupdate', 'port', '6600'))
        options['password'] = \
            ui.config_val(config, 'mpdupdate', 'password', '')

@MPDUpdatePlugin.listen('save')
def update(lib=None):
    update_mpd(options['host'], options['port'], options['password'])
