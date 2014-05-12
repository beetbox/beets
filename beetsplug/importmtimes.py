"""Preserve file modification times during copy imports.

File modification times are also stored in the `added` field.
"""

from __future__ import unicode_literals, absolute_import, print_function

import logging, os

from beets import config
from beets import util
from beets.plugins import BeetsPlugin

log = logging.getLogger('beets')

class ImportMtimesPlugin(BeetsPlugin):
    pass

@ImportMtimesPlugin.listen('import_task_start')
def check_config(task, session):
    if not config['import']['copy']:
        raise ValueError('The importmtimes plugin can only be used for copy'
                         ' imports')

def copy_mtime(source_path, dest_path):
    """Copy the file mtime from the source path to the destination path.
    """
    source_stat = os.stat(util.syspath(source_path))
    dest_stat = os.stat(util.syspath(dest_path))
    os.utime(util.syspath(dest_path),
             (dest_stat.st_atime, source_stat.st_mtime))

# key: item path in the library
# value: file outside the library from which the item was imported
item_source_paths = dict()

def preserve_mtime(item):
    """Preserve the file modification time of an imported item by copying the
    mtime from the file that the item is copied from.
    """
    source_path = item_source_paths.get(item.path)
    if source_path is None:
        log.warn("No import source path found for item "
                 + util.displayable_path(item.path))
        return

    copy_mtime(source_path, item.path)
    item.mtime = os.path.getmtime(util.syspath(item.path))
    del item_source_paths[item.path]

@ImportMtimesPlugin.listen('item_copied')
def record_import_source_path(item, source, destination):
    """Record which file an imported item is copied from.
    """
    if (source == destination):
        return

    item_source_paths[destination] = source
    log.debug('Recorded item source path "%s" <- "%s"',
              util.displayable_path(destination),
              util.displayable_path(source))

@ImportMtimesPlugin.listen('album_imported')
def update_album_times(lib, album):
    for item in album.items():
        preserve_mtime(item)
        item.store()

    item_mtimes = (item.mtime for item in album.items() if item.mtime > 0)
    album.added = min(item_mtimes)
    album.store()

@ImportMtimesPlugin.listen('item_imported')
def update_item_times(lib, item):
    preserve_mtime(item)
    item.added = item.mtime
    item.store()
