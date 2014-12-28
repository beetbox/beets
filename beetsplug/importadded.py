"""Populate an item's `added` and `mtime` fields by using the file
modification time (mtime) of the item's source file before import.

Reimported albums and items are skipped.
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

# item.id for new items that were reimported
reimported_item_ids = None

# album.path for old albums that were replaced by a new reimported album
replaced_album_paths = None


def reimported_item(item):
    return item.id in reimported_item_ids


def reimported_album(album):
    return album.path in replaced_album_paths


@ImportAddedPlugin.listen('import_task_start')
def record_if_inplace(task, session):
    if not (session.config['copy'] or session.config['move'] or
            session.config['link']):
        log.debug(u"In place import detected, recording mtimes from source"
                  u" paths")
        for item in task.items:
            record_import_mtime(item, item.path, item.path)


@ImportAddedPlugin.listen('import_task_files')
def record_reimported(task, session):
    global reimported_item_ids, replaced_album_paths
    reimported_item_ids = set([item.id for item, replaced_items
                               in task.replaced_items.iteritems()
                               if replaced_items])
    replaced_album_paths = set(task.replaced_albums.keys())


def write_file_mtime(path, mtime):
    """Write the given mtime to the destination path.
    """
    stat = os.stat(util.syspath(path))
    os.utime(util.syspath(path),
             (stat.st_atime, mtime))


def write_item_mtime(item, mtime):
    """Write the given mtime to an item's `mtime` field and to the mtime of the
    item's file.
    """
    if mtime is None:
        log.warn(u"No mtime to be preserved for item '{0}'"
                 .format(util.displayable_path(item.path)))
        return

    # The file's mtime on disk must be in sync with the item's mtime
    write_file_mtime(util.syspath(item.path), mtime)
    item.mtime = mtime


# key: item path in the library
# value: the file mtime of the file the item was imported from
item_mtime = dict()


@ImportAddedPlugin.listen('before_item_moved')
@ImportAddedPlugin.listen('item_copied')
@ImportAddedPlugin.listen('item_linked')
def record_import_mtime(item, source, destination):
    """Record the file mtime of an item's path before its import.
    """
    mtime = os.stat(util.syspath(source)).st_mtime
    item_mtime[destination] = mtime
    log.debug(u"Recorded mtime {0} for item '{1}' imported from '{2}'".format(
        mtime, util.displayable_path(destination),
        util.displayable_path(source)))


@ImportAddedPlugin.listen('album_imported')
def update_album_times(lib, album):
    if reimported_album(album):
        log.debug(u"Album '{0}' is reimported, skipping import of added dates"
                  u" for the album and its items."
                  .format(util.displayable_path(album.path)))
        return

    album_mtimes = []
    for item in album.items():
        mtime = item_mtime.pop(item.path, None)
        if mtime:
            album_mtimes.append(mtime)
            if config['importadded']['preserve_mtimes'].get(bool):
                write_item_mtime(item, mtime)
                item.store()
    album.added = min(album_mtimes)
    log.debug(u"Import of album '{0}', selected album.added={1} from item"
              u" file mtimes.".format(album.album, album.added))
    album.store()


@ImportAddedPlugin.listen('item_imported')
def update_item_times(lib, item):
    if reimported_item(item):
        log.debug(u"Item '{0}' is reimported, skipping import of added "
                  u"date.".format(util.displayable_path(item.path)))
        return
    mtime = item_mtime.pop(item.path, None)
    if mtime:
        item.added = mtime
        if config['importadded']['preserve_mtimes'].get(bool):
            write_item_mtime(item, mtime)
        log.debug(u"Import of item '{0}', selected item.added={1}"
                  .format(util.displayable_path(item.path), item.added))
        item.store()
