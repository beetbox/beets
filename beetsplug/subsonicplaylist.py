# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2019, Joris Jensen
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

from __future__ import absolute_import, division, print_function

import os
from hashlib import md5
import xml.etree.ElementTree as ET
import random
import string
import requests
from beets.util import normpath, bytestring_path, mkdirall, syspath, \
    path_as_posix

from beets.ui import Subcommand

from beets.plugins import BeetsPlugin

__author__ = 'https://github.com/MrNuggelz'


class SubsonicPlaylistPlugin(BeetsPlugin):

    def __init__(self):
        super(SubsonicPlaylistPlugin, self).__init__()
        self.config.add(
            {
                'relative_to': None,
                'playlist_dir': '.',
                'forward_slash': False,
                'playlist_ids': [],
                'playlist_names': [],
                'username': '',
                'password': ''
            }
        )
        self.config['password'].redact = True

    def create_playlist(self, xml, lib):
        relative_to = self.config['relative_to'].get()
        if relative_to:
            relative_to = normpath(relative_to)

        playlist = ET.fromstring(xml)[0]
        if playlist.attrib.get('code', '200') != '200':
            alt_error = 'error getting playlist, but no error message found'
            self._log.warn(playlist.attrib.get('message', alt_error))
            return
        name = '{}.m3u'.format()
        tracks = [(t.attrib['artist'], t.attrib['album'], t.attrib['title'])
                  for t in playlist]
        track_paths = []
        for t in tracks:
            query = 'artist:"{}" album:"{}" title:"{}"'.format(*t)
            items = lib.items(query)
            if len(items) > 0:
                item_path = items[0].path
                if relative_to:
                    item_path = os.path.relpath(items[0].path, relative_to)
                track_paths.append(item_path)
            else:
                self._log.warn(u"{} | track not found ({})", name, query)
        # write playlist
        playlist_dir = self.config['playlist_dir'].as_filename()
        playlist_dir = bytestring_path(playlist_dir)
        m3u_path = normpath(os.path.join(playlist_dir, bytestring_path(name)))
        mkdirall(m3u_path)
        with open(syspath(m3u_path), 'wb') as f:
            for path in track_paths:
                if self.config['forward_slash'].get():
                    path = path_as_posix(path)
                f.write(path + b'\n')

    def get_playlist_by_id(self, playlist_id, lib):
        xml = self.send('getPlaylist', '&id={}'.format(playlist_id)).text
        self.create_playlist(xml, lib)

    def commands(self):
        def build_playlist(lib, opts, args):

            if len(self.config['playlist_ids'].as_str_seq()) > 0:
                for playlist_id in self.config['playlist_ids'].as_str_seq():
                    self.get_playlist_by_id(playlist_id, lib)
            if len(self.config['playlist_names'].as_str_seq()) > 0:
                playlists = ET.fromstring(self.send('getPlaylists').text)[0]
                if playlists.attrib.get('code', '200') != '200':
                    alt_error = 'error getting playlists,' \
                                ' but no erro message found'
                    self._log.warn(playlists.attrib.get('message', alt_error))
                    return
                for name in self.config['playlist_names'].as_str_seq():
                    for playlist in playlists:
                        if name == playlist.attrib['name']:
                            self.get_playlist_by_id(playlist.attrib['id'], lib)

        subsonicplaylist_cmds = Subcommand(
            'subsonicplaylist', help=u'import a subsonic playlist'
        )
        subsonicplaylist_cmds.func = build_playlist
        return [subsonicplaylist_cmds]

    def generate_token(self):
        salt = ''.join(random.choices(string.ascii_lowercase + string.digits))
        return md5(
            (self.config['password'].get() + salt).encode()).hexdigest(), salt

    def send(self, endpoint, params=''):
        url = '{}/rest/{}?u={}&t={}&s={}&v=1.12.0&c=beets'.format(
            self.config['base_url'].get(),
            endpoint,
            self.config['username'],
            *self.generate_token())
        resp = requests.get(url + params)
        return resp
