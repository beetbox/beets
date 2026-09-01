"""Populate an item's `added` and `mtime` fields by using the file
modification time (mtime) of the item's source file before import.

Reimported albums and items are skipped.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from beets import importer, util
from beets.plugins import BeetsPlugin

if TYPE_CHECKING:
    from beets.importer import ImportSession, ImportTask
    from beets.library import Album, Item, Library


class ImportAddedPlugin(BeetsPlugin):
    item_mtime: dict[bytes, float]
    reimported_item_ids: set[int | None]
    replaced_album_paths: set[bytes]

    def __init__(self) -> None:
        super().__init__()
        self.config.add(
            {"preserve_mtimes": False, "preserve_write_mtimes": False}
        )

        # item.id for new items that were reimported
        self.reimported_item_ids = set()
        # album.path for old albums that were replaced by a reimported album
        self.replaced_album_paths = set()
        # item path in the library to the mtime of the source file
        self.item_mtime = {}

        register = self.register_listener
        register("import_task_created", self.check_config)
        register("import_task_created", self.record_if_inplace)
        register("import_task_files", self.record_reimported)
        register("before_item_moved", self.record_import_mtime)
        register("item_copied", self.record_import_mtime)
        register("item_linked", self.record_import_mtime)
        register("item_hardlinked", self.record_import_mtime)
        register("item_reflinked", self.record_import_mtime)
        register("album_imported", self.update_album_times)
        register("item_imported", self.update_item_times)
        register("after_write", self.update_after_write_time)

    def check_config(
        self, task: ImportTask, session: ImportSession
    ) -> list[ImportTask] | None:
        self.config["preserve_mtimes"].get(bool)
        return None

    def reimported_item(self, item: Item) -> bool:
        return item.id in self.reimported_item_ids

    def reimported_album(self, album: Album) -> bool:
        return album.path in self.replaced_album_paths

    def record_if_inplace(
        self, task: ImportTask, session: ImportSession
    ) -> list[ImportTask] | None:
        if not (
            session.config["copy"]
            or session.config["move"]
            or session.config["link"]
            or session.config["hardlink"]
            or session.config["reflink"]
        ):
            self._log.debug(
                "In place import detected, recording mtimes from source paths"
            )
            items = (
                [task.item]
                if isinstance(task, importer.SingletonImportTask)
                else task.items
            )
            for item in items:
                self.record_import_mtime(item, item.path, item.path)

        return None

    def record_reimported(
        self, task: ImportTask, session: ImportSession
    ) -> None:
        self.reimported_item_ids = {
            item.id
            for item, replaced_items in task.replaced_items.items()
            if replaced_items
        }
        self.replaced_album_paths = set(task.replaced_albums.keys())

    def write_file_mtime(self, path: str, mtime: float) -> None:
        """Write the given mtime to the destination path."""
        stat = os.stat(util.syspath(path))
        os.utime(util.syspath(path), (stat.st_atime, mtime))

    def write_item_mtime(self, item: Item, mtime: float) -> None:
        """Write the given mtime to an item's `mtime` field and to the mtime
        of the item's file.
        """
        # The file's mtime on disk must be in sync with the item's mtime
        self.write_file_mtime(util.syspath(item.path), mtime)
        item.mtime = int(mtime)

    def record_import_mtime(
        self, item: Item, source: bytes, destination: bytes
    ) -> None:
        """Record the file mtime of an item's path before its import."""
        mtime = os.stat(util.syspath(source)).st_mtime
        self.item_mtime[destination] = mtime
        self._log.debug(
            "Recorded mtime {} for item '{}' imported from '{}'",
            mtime,
            util.displayable_path(destination),
            util.displayable_path(source),
        )

    def update_album_times(self, lib: Library, album: Album) -> None:
        if self.reimported_album(album):
            self._log.debug(
                "Album '{.filepath}' is reimported, skipping import of "
                "added dates for the album and its items.",
                album,
            )
            return

        album_mtimes = []
        for item in album.items():
            mtime = self.item_mtime.pop(item.path, None)
            if mtime:
                album_mtimes.append(mtime)
                if self.config["preserve_mtimes"].get(bool):
                    self.write_item_mtime(item, mtime)
                    item.store()
        album.added = min(album_mtimes)
        self._log.debug(
            "Import of album '{0.album}', selected album.added={0.added} "
            "from item file mtimes.",
            album,
        )
        album.store()

    def update_item_times(self, lib: Library, item: Item) -> None:
        if self.reimported_item(item):
            self._log.debug(
                "Item '{.filepath}' is reimported, skipping import of added date.",
                item,
            )
            return
        mtime = self.item_mtime.pop(item.path, None)
        if mtime:
            item.added = mtime
            if self.config["preserve_mtimes"].get(bool):
                self.write_item_mtime(item, mtime)
            self._log.debug(
                "Import of item '{0.filepath}', selected item.added={0.added}",
                item,
            )
            item.store()

    def update_after_write_time(self, item: Item, path: bytes) -> None:
        """Update the mtime of the item's file with the item.added value
        after each write of the item if `preserve_write_mtimes` is enabled.
        """
        if item.added:
            if self.config["preserve_write_mtimes"].get(bool):
                self.write_item_mtime(item, item.added)
            self._log.debug(
                "Write of item '{0.filepath}', selected item.added={0.added}",
                item,
            )
