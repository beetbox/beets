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

from hashlib import md5
import xml.etree.ElementTree as ET
import random
import string
from urllib.parse import urlencode

import requests
from beets.dbcore.query import SubstringQuery

from beets.dbcore import AndQuery, Query, MatchQuery

from beets import plugins

from beets.ui import Subcommand

from beets.plugins import BeetsPlugin

__author__ = 'https://github.com/MrNuggelz'


class SubsonicPlaylistPlugin(BeetsPlugin):

    def __init__(self):
        super(SubsonicPlaylistPlugin, self).__init__()
        self.config.add(
            {
                'delete': False,
                'playlist_ids': [],
                'playlist_names': [],
                'username': '',
                'password': ''
            }
        )
        self.config['password'].redact = True

    def update_tags(self, playlist_dict, lib):
        with lib.transaction():
            for query, playlist_tag in playlist_dict.items():
                query = AndQuery([SubstringQuery("artist", query[0]),
                                  SubstringQuery("album", query[1]),
                                  SubstringQuery("title", query[2])])
                items = lib.items(query)
                if not items:
                    self._log.warn(u"{} | track not found ({})", playlist_tag,
                                   query)
                    continue
                for item in items:
                    item.subsonic_playlist = playlist_tag
                    item.try_sync(write=True, move=False)

    def get_playlist(self, playlist_id):
        xml = self.send('getPlaylist', {'id': playlist_id}).text
        playlist = ET.fromstring(xml)[0]
        if playlist.attrib.get('code', '200') != '200':
            alt_error = 'error getting playlist, but no error message found'
            self._log.warn(playlist.attrib.get('message', alt_error))
            return

        name = playlist.attrib.get('name', 'undefined')
        tracks = [(t.attrib['artist'], t.attrib['album'], t.attrib['title'])
                  for t in playlist]
        return name, tracks

    def commands(self):
        def build_playlist(lib, opts, args):
            self.config.set_args(opts)
            ids = self.config['playlist_ids'].as_str_seq()
            if len(self.config['playlist_names'].as_str_seq()) > 0:
                playlists = ET.fromstring(self.send('getPlaylists').text)[
                    0]
                if playlists.attrib.get('code', '200') != '200':
                    alt_error = 'error getting playlists,' \
                                ' but no erro message found'
                    self._log.warn(
                        playlists.attrib.get('message', alt_error))
                    return
                for name in self.config['playlist_names'].as_str_seq():
                    for playlist in playlists:
                        if name == playlist.attrib['name']:
                            ids.append(playlist.attrib['id'])
            playlist_dict = dict()
            for playlist_id in ids:
                name, tracks = self.get_playlist(playlist_id)
                for track in tracks:
                    if track not in playlist_dict:
                        playlist_dict[track] = ';'
                    playlist_dict[track] += name + ';'
            # delete old tags
            if self.config['delete']:
                for item in lib.items('subsonic_playlist:";"'):
                    item.update({'subsonic_playlist': ''})
                    with lib.transaction():
                        item.try_sync(write=True, move=False)

            self.update_tags(playlist_dict, lib)

        subsonicplaylist_cmds = Subcommand(
            'subsonicplaylist', help=u'import a subsonic playlist'
        )
        subsonicplaylist_cmds.parser.add_option(
            u'-d',
            u'--delete',
            action='store_true',
            help=u'delete tag from items not in any playlist anymore',
        )
        subsonicplaylist_cmds.func = build_playlist
        return [subsonicplaylist_cmds]

    def generate_token(self):
        salt = ''.join(random.choices(string.ascii_lowercase + string.digits))
        return md5(
            (self.config['password'].get() + salt).encode()).hexdigest(), salt

    def send(self, endpoint, params=None):
        if params is None:
            params = dict()
        url = '{}/rest/{}?u={}&t={}&s={}&v=1.12.0&c=beets'.format(
            self.config['base_url'].get(),
            endpoint,
            self.config['username'],
            *self.generate_token())
        resp = requests.get(url + urlencode(params))
        return resp
