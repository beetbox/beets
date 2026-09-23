"""Load SQLite extensions."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from beets.dbcore import Database
from beets.plugins import BeetsPlugin

if TYPE_CHECKING:
    from beets.library import Library


class LoadExtPlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()

        if not Database.supports_extensions:
            self._log.warning(
                "loadext is enabled but the current SQLite "
                "installation does not support extensions"
            )
            return

        self.register_listener("library_opened", self.library_opened)

    def library_opened(self, lib: Library) -> None:
        for v in self.config.sequence():
            ext = v.as_filename()

            self._log.debug("loading extension {}", ext)

            try:
                lib.load_extension(ext)
            except sqlite3.OperationalError as e:
                self._log.error("failed to load extension {}: {}", ext, e)
