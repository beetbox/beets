# -*- coding: utf-8 -*-

"""Populate an item's `added` and `mtime` fields by using the file
modification time (mtime) of the item's source file before import.

Reimported albums and items are skipped.
"""
from __future__ import division, absolute_import, print_function

import os

from beets import util
from beets import importer
from beets.plugins import BeetsPlugin


class ImportAddedPlugin(BeetsPlugin):
    def __init__(self):
        super(ImportAddedPlugin, self).__init__()
        self.config.add({
            'preserve_mtimes': False,
            'preserve_write_mtimes': False,
        })

        # item.id for new items that were reimported
        self.reimported_item_ids = None
        # album.path for old albums that were replaced by a reimported album
        self.replaced_album_paths = None
        # item path in the library to the mtime of the source file
        self.item_mtime = dict()

        register = self.register_listener
        register('import_task_start', self.check_config)
        register('import_task_start', self.record_if_inplace)
        register('import_task_files', self.record_reimported)
        register('before_item_moved', self.record_import_mtime)
        register('item_copied', self.record_import_mtime)
        register('item_linked', self.record_import_mtime)
        register('item_hardlinked', self.record_import_mtime)
        register('album_imported', self.update_album_times)
        register('item_imported', self.update_item_times)
        register('after_write', self.update_after_write_time)

    def check_config(self, task, session):
        self.config['preserve_mtimes'].get(bool)

    def reimported_item(self, item):
        return item.id in self.reimported_item_ids

    def reimported_album(self, album):
        return album.path in self.replaced_album_paths

    def record_if_inplace(self, task, session):
        if not (session.config['copy'] or session.config['move'] or
                session.config['link'] or session.config['hardlink']):
            self._log.debug(u"In place import detected, recording mtimes from "
                            u"source paths")
            items = [task.item] \
                if isinstance(task, importer.SingletonImportTask) \
                else task.items
            for item in items:
                self.record_import_mtime(item, item.path, item.path)

    def record_reimported(self, task, session):
        self.reimported_item_ids = set(item.id for item, replaced_items
                                       in task.replaced_items.items()
                                       if replaced_items)
        self.replaced_album_paths = set(task.replaced_albums.keys())

    def write_file_mtime(self, path, mtime):
        """Write the given mtime to the destination path.
        """
        stat = os.stat(util.syspath(path))
        os.utime(util.syspath(path), (stat.st_atime, mtime))

    def write_item_mtime(self, item, mtime):
        """Write the given mtime to an item's `mtime` field and to the mtime
        of the item's file.
        """
        # The file's mtime on disk must be in sync with the item's mtime
        self.write_file_mtime(util.syspath(item.path), mtime)
        item.mtime = mtime

    def record_import_mtime(self, item, source, destination):
        """Record the file mtime of an item's path before its import.
        """
        mtime = os.stat(util.syspath(source)).st_mtime
        self.item_mtime[destination] = mtime
        self._log.debug(u"Recorded mtime {0} for item '{1}' imported from "
                        u"'{2}'", mtime, util.displayable_path(destination),
                        util.displayable_path(source))

    def update_album_times(self, lib, album):
        if self.reimported_album(album):
            self._log.debug(u"Album '{0}' is reimported, skipping import of "
                            u"added dates for the album and its items.",
                            util.displayable_path(album.path))
            return

        album_mtimes = []
        for item in album.items():
            mtime = self.item_mtime.pop(item.path, None)
            if mtime:
                album_mtimes.append(mtime)
                if self.config['preserve_mtimes'].get(bool):
                    self.write_item_mtime(item, mtime)
                    item.store()
        album.added = min(album_mtimes)
        self._log.debug(u"Import of album '{0}', selected album.added={1} "
                        u"from item file mtimes.", album.album, album.added)
        album.store()

    def update_item_times(self, lib, item):
        if self.reimported_item(item):
            self._log.debug(u"Item '{0}' is reimported, skipping import of "
                            u"added date.", util.displayable_path(item.path))
            return
        mtime = self.item_mtime.pop(item.path, None)
        if mtime:
            item.added = mtime
            if self.config['preserve_mtimes'].get(bool):
                self.write_item_mtime(item, mtime)
            self._log.debug(u"Import of item '{0}', selected item.added={1}",
                            util.displayable_path(item.path), item.added)
            item.store()

    def update_after_write_time(self, item):
        """Update the mtime of the item's file with the item.added value
        after each write of the item if `preserve_write_mtimes` is enabled.
        """
        if item.added:
            if self.config['preserve_write_mtimes'].get(bool):
                self.write_item_mtime(item, item.added)
            self._log.debug(u"Write of item '{0}', selected item.added={1}",
                            util.displayable_path(item.path), item.added)
