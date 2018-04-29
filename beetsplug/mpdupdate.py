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

"""Updates an MPD index whenever the library is changed.

Put something like the following in your config.yaml to configure:
    mpd:
        host: localhost
        port: 6600
        password: seekrit
"""
from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
import os
import socket
from beets import config
import six


# No need to introduce a dependency on an MPD library for such a
# simple use case. Here's a simple socket abstraction to make things
# easier.
class BufferedSocket(object):
    """Socket abstraction that allows reading by line."""
    def __init__(self, host, port, sep=b'\n'):
        if host[0] in ['/', '~']:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(os.path.expanduser(host))
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
        self.buf = b''
        self.sep = sep

    def readline(self):
        while self.sep not in self.buf:
            data = self.sock.recv(1024)
            if not data:
                break
            self.buf += data
        if self.sep in self.buf:
            res, self.buf = self.buf.split(self.sep, 1)
            return res + self.sep
        else:
            return b''

    def send(self, data):
        self.sock.send(data)

    def close(self):
        self.sock.close()


class MPDUpdatePlugin(BeetsPlugin):
    def __init__(self):
        super(MPDUpdatePlugin, self).__init__()
        config['mpd'].add({
            'host':     os.environ.get('MPD_HOST', u'localhost'),
            'port':     6600,
            'password': u'',
        })
        config['mpd']['password'].redact = True

        # For backwards compatibility, use any values from the
        # plugin-specific "mpdupdate" section.
        for key in config['mpd'].keys():
            if self.config[key].exists():
                config['mpd'][key] = self.config[key].get()

        self.register_listener('database_change', self.db_change)

    def db_change(self, lib, model):
        self.register_listener('cli_exit', self.update)

    def update(self, lib):
        self.update_mpd(
            config['mpd']['host'].as_str(),
            config['mpd']['port'].get(int),
            config['mpd']['password'].as_str(),
        )

    def update_mpd(self, host='localhost', port=6600, password=None):
        """Sends the "update" command to the MPD server indicated,
        possibly authenticating with a password first.
        """
        self._log.info('Updating MPD database...')

        try:
            s = BufferedSocket(host, port)
        except socket.error as e:
            self._log.warning(u'MPD connection failed: {0}',
                              six.text_type(e.strerror))
            return

        resp = s.readline()
        if b'OK MPD' not in resp:
            self._log.warning(u'MPD connection failed: {0!r}', resp)
            return

        if password:
            s.send(b'password "%s"\n' % password.encode('utf8'))
            resp = s.readline()
            if b'OK' not in resp:
                self._log.warning(u'Authentication failed: {0!r}', resp)
                s.send(b'close\n')
                s.close()
                return

        s.send(b'update\n')
        resp = s.readline()
        if b'updating_db' not in resp:
            self._log.warning(u'Update failed: {0!r}', resp)

        s.send(b'close\n')
        s.close()
        self._log.info(u'Database updated.')
