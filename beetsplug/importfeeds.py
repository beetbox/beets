# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Fabrice Laporte.
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

"""Write paths of imported files in various formats to ease later import in a
music player. Also allow printing the new file locations to stdout in case
one wants to manually add music to a player by its path.
"""
import datetime
import os
import re

from beets.plugins import BeetsPlugin
from beets.util import mkdirall, normpath, syspath, bytestring_path, link
from beets import config

M3U_DEFAULT_NAME = 'imported.m3u'


def _get_feeds_dir(lib):
    """Given a Library object, return the path to the feeds directory to be
    used (either in the library directory or an explicitly configured
    path). Ensures that the directory exists.
    """
    # Inside library directory.
    dirpath = lib.directory

    # Ensure directory exists.
    if not os.path.exists(syspath(dirpath)):
        os.makedirs(syspath(dirpath))
    return dirpath


def _build_m3u_filename(basename):
    """Builds unique m3u filename by appending given basename to current
    date."""

    basename = re.sub(r"[\s,/\\'\"]", '_', basename)
    date = datetime.datetime.now().strftime("%Y%m%d_%Hh%M")
    path = normpath(os.path.join(
        config['importfeeds']['dir'].as_filename(),
        date + '_' + basename + '.m3u'
    ))
    return path


def _write_m3u(m3u_path, items_paths):
    """Append relative paths to items into m3u file.
    """
    mkdirall(m3u_path)
    with open(syspath(m3u_path), 'ab') as f:
        for path in items_paths:
            f.write(path + b'\n')


class ImportFeedsPlugin(BeetsPlugin):
    def __init__(self):
        super(ImportFeedsPlugin, self).__init__()

        self.config.add({
            'formats': [],
            'm3u_name': u'imported.m3u',
            'dir': None,
            'relative_to': None,
            'absolute_path': False,
        })

        feeds_dir = self.config['dir'].get()
        if feeds_dir:
            feeds_dir = os.path.expanduser(bytestring_path(feeds_dir))
            self.config['dir'] = feeds_dir
            if not os.path.exists(syspath(feeds_dir)):
                os.makedirs(syspath(feeds_dir))

        relative_to = self.config['relative_to'].get()
        if relative_to:
            self.config['relative_to'] = normpath(relative_to)
        else:
            self.config['relative_to'] = feeds_dir

        self.register_listener('library_opened', self.library_opened)
        self.register_listener('album_imported', self.album_imported)
        self.register_listener('item_imported', self.item_imported)

    def _record_items(self, lib, basename, items):
        """Records relative paths to the given items for each feed format
        """
        feedsdir = bytestring_path(self.config['dir'].as_filename())
        formats = self.config['formats'].as_str_seq()
        relative_to = self.config['relative_to'].get() \
            or self.config['dir'].as_filename()
        relative_to = bytestring_path(relative_to)

        paths = []
        for item in items:
            if self.config['absolute_path']:
                paths.append(item.path)
            else:
                try:
                    relpath = os.path.relpath(item.path, relative_to)
                except ValueError:
                    # On Windows, it is sometimes not possible to construct a
                    # relative path (if the files are on different disks).
                    relpath = item.path
                paths.append(relpath)

        if 'm3u' in formats:
            m3u_basename = bytestring_path(
                self.config['m3u_name'].as_str())
            m3u_path = os.path.join(feedsdir, m3u_basename)
            _write_m3u(m3u_path, paths)

        if 'm3u_multi' in formats:
            m3u_path = _build_m3u_filename(basename)
            _write_m3u(m3u_path, paths)

        if 'link' in formats:
            for path in paths:
                dest = os.path.join(feedsdir, os.path.basename(path))
                if not os.path.exists(syspath(dest)):
                    link(path, dest)

        if 'echo' in formats:
            self._log.info(u"Location of imported music:")
            for path in paths:
                self._log.info(u"  {0}", path)

    def library_opened(self, lib):
        if self.config['dir'].get() is None:
            self.config['dir'] = _get_feeds_dir(lib)

    def album_imported(self, lib, album):
        self._record_items(lib, album.album, album.items())

    def item_imported(self, lib, item):
        self._record_items(lib, item.title, [item])
