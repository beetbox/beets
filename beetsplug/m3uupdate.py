# This file is part of beets.
# Copyright 2012, Fabrice Laporte.
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

"""Write paths of imported files in a m3u file to ease later import in a
music player.
"""

from __future__ import with_statement
import os

from beets import ui
from beets.plugins import BeetsPlugin
from beets.util import normpath

DEFAULT_FILENAME = 'imported.m3u'
_m3u_path = None  # If unspecified, use file in library directory.

class m3uPlugin(BeetsPlugin):
    def configure(self, config):
        global _m3u_path
        _m3u_path = ui.config_val(config, 'm3uupdate', 'm3u', None)
        if _m3u_path:
            _m3u_path = normpath(_m3u_path)

def _get_m3u_path(lib):
    """Given a Library object, return the path to the M3U file to be
    used (either in the library directory or an explicitly configured
    path. Ensures that the containing directory exists.
    """
    if _m3u_path:
        # Explicitly specified.
        path = _m3u_path
    else:
        # Inside library directory.
        path = os.path.join(lib.directory, DEFAULT_FILENAME)

    # Ensure containing directory exists.
    m3u_dir = os.path.dirname(path)
    if not os.path.exists(m3u_dir):
        os.makedirs(m3u_dir)

    return path

def _record_items(lib, items):
    """Records relative paths to the given items in the appropriate M3U
    file.
    """
    m3u_path = _get_m3u_path(lib)
    with open(m3u_path, 'a') as f:
        for item in items:
            path = os.path.relpath(item.path, os.path.dirname(m3u_path))
            f.write(path + '\n')

@m3uPlugin.listen('album_imported')
def album_imported(lib, album, config):
    _record_items(lib, album.items())

@m3uPlugin.listen('item_imported')
def item_imported(lib, item, config):
    _record_items(lib, [item])
