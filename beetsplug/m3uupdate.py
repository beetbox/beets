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
import datetime
import os
import sys
import re

from beets import ui
from beets.plugins import BeetsPlugin
from beets.util import normpath

_m3u_dirpath = None  # If unspecified, use file in library directory.

class m3uPlugin(BeetsPlugin):
    def configure(self, config):
        global _m3u_dirpath, _m3u_fixedname
        _m3u_dirpath = ui.config_val(config, 'm3uupdate', 'm3u_dirpath', None)

        if _m3u_dirpath:
            _m3u_dirpath = normpath(_m3u_dirpath)

        _m3u_fixedname = ui.config_val(config, 'm3uupdate', 'm3u_fixedname', None)

def _get_m3u_dirpath(lib):
    """Given a Library object, return the path to the M3U file to be
    used (either in the library directory or an explicitly configured
    path. Ensures that the containing directory exists.
    """
    if _m3u_dirpath:
        # Explicitly specified.
        dirpath = _m3u_dirpath
    else:
        # Inside library directory.
        dirpath = lib.directory

    # Ensure directory exists.
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)

    return dirpath

def _build_filename(lib, basename):
    """Builds unique basename for the M3U file."""
    if _m3u_fixedname:
        path = os.path.join(_get_m3u_dirpath(lib), _m3u_fixedname) 
    else :
        m3u_dirpath = _get_m3u_dirpath(lib)
        basename = re.sub(r"[\s,'\"]", '_', basename)
        date = datetime.datetime.now().strftime("%Y%m%d_%Hh%M")
        path = normpath(os.path.join(m3u_dirpath, date+'_'+basename+'.m3u'))
    return path

def _record_items(m3u_path, items):
    """Records relative paths to the given items in the appropriate M3U
    file.
    """
    with open(m3u_path, 'a') as f:
        for item in items:
            path = os.path.relpath(item.path, os.path.dirname(m3u_path))
            f.write(path + '\n')

@m3uPlugin.listen('album_imported')
def album_imported(lib, album, config):
    _record_items(_build_filename(lib, album.album), album.items())

@m3uPlugin.listen('item_imported')
def item_imported(lib, item, config):
    _record_items(_build_filename(lib, item.title), [item])
