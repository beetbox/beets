# This file is part of beets.
# Copyright 2013, Fabrice Laporte.
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
import datetime
import os
import re

from beets.plugins import BeetsPlugin
from beets.util import normpath, syspath, bytestring_path
from beets import config

M3U_DEFAULT_NAME = 'imported.m3u'


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
    with open(syspath(m3u_path), 'a') as f:
        for path in items_paths:
            f.write(path + '\n')


def _record_items(lib, basename, items):
    """Records relative paths to the given items for each feed format
    """
    feedsdir = bytestring_path(config['importfeeds']['dir'].as_filename())
    formats = config['importfeeds']['formats'].as_str_seq()
    relative_to = config['importfeeds']['relative_to'].get() \
        or config['importfeeds']['dir'].as_filename()
    relative_to = bytestring_path(relative_to)

    paths = []
    for item in items:
        if config['importfeeds']['absolute_path']:
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
        basename = bytestring_path(
            config['importfeeds']['m3u_name'].get(unicode)
        )
        m3u_path = os.path.join(feedsdir, basename)
        _write_m3u(m3u_path, paths)

    if 'm3u_multi' in formats:
        m3u_path = _build_m3u_filename(basename)
        _write_m3u(m3u_path, paths)

    if 'link' in formats:
        for path in paths:
            dest = os.path.join(feedsdir, os.path.basename(path))
            if not os.path.exists(syspath(dest)):
                os.symlink(syspath(path), syspath(dest))


@ImportFeedsPlugin.listen('library_opened')
def library_opened(lib):
    if config['importfeeds']['dir'].get() is None:
        config['importfeeds']['dir'] = _get_feeds_dir(lib)


@ImportFeedsPlugin.listen('album_imported')
def album_imported(lib, album):
    _record_items(lib, album.album, album.items())


@ImportFeedsPlugin.listen('item_imported')
def item_imported(lib, item):
    _record_items(lib, item.title, [item])
