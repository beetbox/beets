"""Populate an items `added` and `mtime` field by using the file modification
time (mtime) of the item's source file before import.
"""

from __future__ import unicode_literals, absolute_import, print_function

import logging
import os

from beets import config
from beets import util
from beets.plugins import BeetsPlugin

log = logging.getLogger('beets')


class ImportAddedPlugin(BeetsPlugin):
    def __init__(self):
        super(ImportAddedPlugin, self).__init__()
        self.config.add({
            'preserve_mtimes': False,
        })


@ImportAddedPlugin.listen('import_task_start')
def check_config(task, session):
    config['importadded']['preserve_mtimes'].get(bool)


def write_file_mtime(path, mtime):
    """Write the given mtime to the destination path.
    """
    stat = os.stat(util.syspath(path))
    os.utime(util.syspath(path),
             (stat.st_atime, mtime))

# key: item path in the library
# value: the file mtime of the file the item was imported from
item_mtime = dict()


def write_item_mtime(item, mtime):
    """Write the given mtime to an item's `mtime` field and to the mtime of the
    item's file.
    """
    if mtime is None:
        log.warn("No mtime to be preserved for item "
                 + util.displayable_path(item.path))
        return

    # The file's mtime on disk must be in sync with the item's mtime
    write_file_mtime(util.syspath(item.path), mtime)
    item.mtime = mtime


@ImportAddedPlugin.listen('before_item_moved')
@ImportAddedPlugin.listen('item_copied')
def record_import_mtime(item, source, destination):
    """Record the file mtime of an item's path before import.
    """
    if (source == destination):
        # Re-import of an existing library item?
        return

    mtime = os.stat(util.syspath(source)).st_mtime
    item_mtime[destination] = mtime
    log.debug('Recorded mtime %s for item "%s" imported from "%s"',
              mtime,
              util.displayable_path(destination),
              util.displayable_path(source))


@ImportAddedPlugin.listen('album_imported')
def update_album_times(lib, album):
    album_mtimes = []
    for item in album.items():
        mtime = item_mtime[item.path]
        if mtime is not None:
            album_mtimes.append(mtime)
            if config['importadded']['preserve_mtimes'].get(bool):
                write_item_mtime(item, mtime)
                item.store()
            del item_mtime[item.path]

    album.added = min(album_mtimes)
    album.store()


@ImportAddedPlugin.listen('item_imported')
def update_item_times(lib, item):
    mtime = item_mtime[item.path]
    if mtime is not None:
        item.added = mtime
        if config['importadded']['preserve_mtimes'].get(bool):
            write_item_mtime(item, mtime)
        item.store()
        del item_mtime[item.path]
