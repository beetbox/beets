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
from beets.library import Item, Album, parse_query_string
from beets.dbcore import OrQuery
from beets.dbcore.query import MultipleSort
import os


class SmartPlaylistPlugin(BeetsPlugin):

    def __init__(self):
        super(SmartPlaylistPlugin, self).__init__()
        self.config.add({
            'relative_to': None,
            'playlist_dir': u'.',
            'auto': True,
            'playlists': []
        })

        self._matched_playlists = None
        self._unmatched_playlists = None

        if self.config['auto']:
            self.register_listener('database_change', self.db_change)

    def commands(self):
        spl_update = ui.Subcommand('splupdate',
                                   help='update the smart playlists. Playlist '
                                        'names may be passed as arguments.')
        spl_update.func = self.update_cmd
        return [spl_update]

    def update_cmd(self, lib, opts, args):
        self.build_queries()
        if args:
            args = set(ui.decargs(args))
            for a in list(args):
                if not a.endswith(".m3u"):
                    args.add("{0}.m3u".format(a))

            playlists = set((name, q, a_q)
                            for name, q, a_q in self._unmatched_playlists
                            if name in args)
            if not playlists:
                raise ui.UserError('No playlist matching any of {0} '
                                   'found'.format([name for name, _, _ in
                                                   self._unmatched_playlists]))

            self._matched_playlists = playlists
            self._unmatched_playlists -= playlists
        else:
            self._matched_playlists = self._unmatched_playlists

        self.update_playlists(lib)

    def build_queries(self):
        """
        Instanciate queries for the playlists.

        Each playlist has 2 queries: one or items one for albums, each with a
        sort. We must also remember its name. _unmatched_playlists is a set of
        tuples (name, (q, q_sort), (album_q, album_q_sort)).

        sort may be any sort, or NullSort, or None. None and NullSort are
        equivalent and both eval to False.
        More precisely
        - it will be NullSort when a playlist query ('query' or 'album_query')
          is a single item or a list with 1 element
        - it will be None when there are multiple items i a query
        """
        self._unmatched_playlists = set()
        self._matched_playlists = set()

        for playlist in self.config['playlists'].get(list):
            playlist_data = (playlist['name'],)
            for key, Model in (('query', Item), ('album_query', Album)):
                qs = playlist.get(key)
                if qs is None:
                    query_and_sort = None, None
                elif isinstance(qs, basestring):
                    query_and_sort = parse_query_string(qs, Model)
                elif len(qs) == 1:
                    query_and_sort = parse_query_string(qs[0], Model)
                else:
                    # multiple queries and sorts
                    queries, sorts = zip(*(parse_query_string(q, Model)
                                           for q in qs))
                    query = OrQuery(queries)
                    final_sorts = []
                    for s in sorts:
                        if s:
                            if isinstance(s, MultipleSort):
                                final_sorts += s.sorts
                            else:
                                final_sorts.append(s)
                    if not final_sorts:
                        sort = None
                    elif len(final_sorts) == 1:
                        sort, = final_sorts
                    else:
                        sort = MultipleSort(final_sorts)
                    query_and_sort = query, sort

                playlist_data += (query_and_sort,)

            self._unmatched_playlists.add(playlist_data)

    def matches(self, model, query, album_query):
        if album_query and isinstance(model, Album):
            return album_query.match(model)
        if query and isinstance(model, Item):
            return query.match(model)
        return False

    def db_change(self, lib, model):
        if self._unmatched_playlists is None:
            self.build_queries()

        for playlist in self._unmatched_playlists:
            n, (q, _), (a_q, _) = playlist
            if self.matches(model, q, a_q):
                self._log.debug("{0} will be updated because of {1}", n, model)
                self._matched_playlists.add(playlist)
                self.register_listener('cli_exit', self.update_playlists)

        self._unmatched_playlists -= self._matched_playlists

    def update_playlists(self, lib):
        self._log.info("Updating {0} smart playlists...",
                       len(self._matched_playlists))

        playlist_dir = self.config['playlist_dir'].as_filename()
        relative_to = self.config['relative_to'].get()
        if relative_to:
            relative_to = normpath(relative_to)

        for playlist in self._matched_playlists:
            name, (query, q_sort), (album_query, a_q_sort) = playlist
            self._log.debug(u"Creating playlist {0}", name)
            items = []

            if query:
                items.extend(lib.items(query, q_sort))
            if album_query:
                for album in lib.albums(album_query, a_q_sort):
                    items.extend(album.items())

            m3us = {}
            # As we allow tags in the m3u names, we'll need to iterate through
            # the items and generate the correct m3u file names.
            for item in items:
                m3u_name = item.evaluate_template(name, True)
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
        self._log.info("{0} playlists updated", len(self._matched_playlists))
