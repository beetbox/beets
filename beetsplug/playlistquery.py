# -*- coding: utf-8 -*-
# This file is part of beets.
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

import os
from beets.plugins import BeetsPlugin
from beets.dbcore import FieldQuery, types
from beets.util.confit import NotFoundError


class PlaylistQuery(FieldQuery):
    """Matches files listed by a playlist file.
    """
    relative_path = None
    playlist_dir = None

    def __init__(self, field, pattern, fast=False):
        super(PlaylistQuery, self).__init__(field, pattern, fast)

        playlist_file = (pattern + '.m3u').encode()
        playlist_path = os.path.join(self.playlist_dir, playlist_file)

        self.paths = []
        with open(playlist_path, 'rb') as f:
            for line in f:
                if line[0] == '#':
                    # ignore comments, and extm3u extension
                    continue
                self.paths.append(os.path.normpath(
                    os.path.join(self.relative_path, line.rstrip())
                ))

    def match(self, item):
        return item.path in self.paths


class PlaylistType(types.String):
    """Custom type for playlist query.
    """
    query = PlaylistQuery


class PlaylistQueryPlugin(BeetsPlugin):
    item_types = {'playlist': PlaylistType()}

    def __init__(self):
        super(PlaylistQueryPlugin, self).__init__()
        self.config.add({
            u'relative_to': 'base'
        })
        self.register_listener('library_opened', self.library_opened)

        PlaylistQuery.playlist_dir = (
            self.config['playlist_dir'].as_filename().encode()
        )

    def library_opened(self, lib):
        relative_to = self.config['relative_to'].as_choice(['base', 'playlist'])

        if relative_to == 'playlist':
            PlaylistQuery.relative_path = PlaylistQuery.playlist_dir
        else:
            PlaylistQuery.relative_path = lib.directory
