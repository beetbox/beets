"""Load SQLite extensions."""

import sqlite3

from beets.dbcore import Database
from beets.plugins import BeetsPlugin


class LoadExtPlugin(BeetsPlugin):
    def __init__(self):
        super().__init__()

        if not Database.supports_extensions:
            self._log.warning(
                "loadext is enabled but the current SQLite "
                "installation does not support extensions"
            )
            return

        self.register_listener("library_opened", self.library_opened)

    def library_opened(self, lib):
        for v in self.config:
            ext = v.as_filename()

            self._log.debug("loading extension {}", ext)

            try:
                lib.load_extension(ext)
            except sqlite3.OperationalError as e:
                self._log.error("failed to load extension {}: {}", ext, e)
