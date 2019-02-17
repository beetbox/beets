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

from __future__ import division, absolute_import, print_function

import os
import fnmatch
import beets


class PlaylistQuery(beets.dbcore.FieldQuery):
    """Matches files listed by a playlist file.
    """
    def __init__(self, field, pattern, fast=True):
        super(PlaylistQuery, self).__init__(field, pattern, fast)
        config = beets.config['playlist']

        # Get the full path to the playlist
        playlist_paths = (
            pattern,
            os.path.abspath(os.path.join(
                config['playlist_dir'].as_filename(),
                '{0}.m3u'.format(pattern),
            )),
        )

        self.paths = []
        for playlist_path in playlist_paths:
            if not fnmatch.fnmatch(playlist_path, '*.[mM]3[uU]'):
                # This is not am M3U playlist, skip this candidate
                continue

            try:
                f = open(beets.util.syspath(playlist_path), mode='rb')
            except (OSError, IOError):
                continue

            if config['relative_to'].get() == 'library':
                relative_to = beets.config['directory'].as_filename()
            elif config['relative_to'].get() == 'playlist':
                relative_to = os.path.dirname(playlist_path)
            else:
                relative_to = config['relative_to'].as_filename()
            relative_to = beets.util.bytestring_path(relative_to)

            for line in f:
                if line[0] == '#':
                    # ignore comments, and extm3u extension
                    continue

                self.paths.append(beets.util.normpath(
                    os.path.join(relative_to, line.rstrip())
                ))
            f.close()
            break

    def col_clause(self):
        if not self.paths:
            # Playlist is empty
            return '0', ()
        clause  = 'path IN ({0})'.format(', '.join('?' for path in self.paths))
        return clause, (beets.library.BLOB_TYPE(p) for p in self.paths)

    def match(self, item):
        return item.path in self.paths


class PlaylistType(beets.dbcore.types.String):
    """Custom type for playlist query.
    """
    query = PlaylistQuery


class PlaylistPlugin(beets.plugins.BeetsPlugin):
    item_types = {'playlist': PlaylistType()}

    def __init__(self):
        super(PlaylistPlugin, self).__init__()
        self.config.add({
            'playlist_dir': '.',
            'relative_to': 'library',
        })
