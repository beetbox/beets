# This file is part of beets.
# Copyright 2015, Dang Mai <contact@dangmai.net>.
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

"""Generates smart playlists based on beets queries.
"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from beets.plugins import BeetsPlugin
from beets import ui
from beets.util import mkdirall, normpath, syspath
import os


def _items_for_query(lib, queries, album):
    """Get the matching items for a list of queries.

    `queries` can either be a single string or a list of strings. In the
    latter case, the results from each query are concatenated. `album`
    indicates whether the queries are item-level or album-level.
    """
    if isinstance(queries, basestring):
        queries = [queries]
    if album:
        for query in queries:
            for album in lib.albums(query):
                for item in album.items():
                    yield item
    else:
        for query in queries:
            for item in lib.items(query):
                yield item


class SmartPlaylistPlugin(BeetsPlugin):
    def __init__(self):
        super(SmartPlaylistPlugin, self).__init__()
        self.config.add({
            'relative_to': None,
            'playlist_dir': u'.',
            'auto': True,
            'playlists': []
        })

        if self.config['auto']:
            self.register_listener('database_change', self.db_change)

    def commands(self):
        def update(lib, opts, args):
            self.update_playlists(lib)
        spl_update = ui.Subcommand('splupdate',
                                   help='update the smart playlists')
        spl_update.func = update
        return [spl_update]

    def db_change(self, lib):
        self.register_listener('cli_exit', self.update_playlists)

    def update_playlists(self, lib):
        self._log.info("Updating smart playlists...")
        playlists = self.config['playlists'].get(list)
        playlist_dir = self.config['playlist_dir'].as_filename()
        relative_to = self.config['relative_to'].get()
        if relative_to:
            relative_to = normpath(relative_to)

        for playlist in playlists:
            self._log.debug(u"Creating playlist {0[name]}", playlist)
            items = []
            if 'album_query' in playlist:
                items.extend(_items_for_query(lib, playlist['album_query'],
                                              True))
            if 'query' in playlist:
                items.extend(_items_for_query(lib, playlist['query'], False))

            m3us = {}
            # As we allow tags in the m3u names, we'll need to iterate through
            # the items and generate the correct m3u file names.
            for item in items:
                m3u_name = item.evaluate_template(playlist['name'], True)
                if m3u_name not in m3us:
                    m3us[m3u_name] = []
                item_path = item.path
                if relative_to:
                    item_path = os.path.relpath(item.path, relative_to)
                if item_path not in m3us[m3u_name]:
                    m3us[m3u_name].append(item_path)
            # Now iterate through the m3us that we need to generate
            for m3u in m3us:
                m3u_path = normpath(os.path.join(playlist_dir, m3u))
                mkdirall(m3u_path)
                with open(syspath(m3u_path), 'w') as f:
                    for path in m3us[m3u]:
                        f.write(path + b'\n')
        self._log.info("{0} playlists updated", len(playlists))
