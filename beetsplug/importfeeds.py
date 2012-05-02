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

"""Write paths of imported files in various formats to ease later import in a
music player.
"""

from __future__ import with_statement
import datetime
import os
import sys
import re

from beets import ui
from beets.plugins import BeetsPlugin
from beets.util import normpath, copy

M3U_DEFAULT_NAME = 'imported.m3u'

class ImportFeedsPlugin(BeetsPlugin):
    def configure(self, config):
        global _feeds_formats, _feeds_dir, _m3u_name

        _feeds_formats = ui.config_val(config, 'importfeeds', 'feeds_formats',
                                       '').split()

        _feeds_dir = ui.config_val(config, 'importfeeds', 'feeds_dir', None)
        _feeds_dir = os.path.expanduser(_feeds_dir)

        _m3u_name = ui.config_val(config, 'importfeeds', 'm3u_name', 
                                 M3U_DEFAULT_NAME)
        
        if _feeds_dir and not os.path.exists(_feeds_dir):
            os.makedirs(_feeds_dir)

def _get_feeds_dir(lib):
    """Given a Library object, return the path to the feeds directory to be
    used (either in the library directory or an explicitly configured
    path). Ensures that the directory exists.
    """
    # Inside library directory.
    dirpath = lib.directory

    # Ensure directory exists.
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)
    return dirpath

def _build_m3u_filename(basename):
    """Builds unique m3u filename by appending given basename to current 
    date."""

    basename = re.sub(r"[\s,'\"]", '_', basename)
    date = datetime.datetime.now().strftime("%Y%m%d_%Hh%M")
    path = normpath(os.path.join(_feeds_dir, date+'_'+basename+'.m3u'))
    return path

def _write_m3u(m3u_path, items_paths):
    """Append relative paths to items into m3u file.
    """
    with open(m3u_path, 'a') as f:
        for path in items_paths:
            f.write(path + '\n')

def _record_items(lib, basename, items):
    """Records relative paths to the given items for each feed format
    """
    global _feeds_dir
    if not _feeds_dir:
        _feeds_dir = _get_feeds_dir(lib)

    paths = []
    for item in items:  
        paths.append(os.path.relpath(item.path, _feeds_dir))

    if 'm3u' in _feeds_formats:
        m3u_path = os.path.join(_feeds_dir, _m3u_name) 
        _write_m3u(m3u_path, paths)
   
    if 'm3u_multi' in _feeds_formats:
        m3u_path = _build_m3u_filename(basename) 
        _write_m3u(m3u_path, paths)

    if 'link' in _feeds_formats:
        for path in paths:
            os.symlink(path, os.path.join(_feeds_dir, os.path.basename(path)))

@ImportFeedsPlugin.listen('album_imported')
def album_imported(lib, album, config):
    _record_items(lib, album.album, album.items())
@ImportFeedsPlugin.listen('item_imported')
def item_imported(lib, item, config):
    _record_items(lib, item.title, [item])
