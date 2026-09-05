"""Creates freedesktop.org-compliant .directory files on an album level."""

from __future__ import annotations

from typing import TYPE_CHECKING

from beets import ui
from beets.plugins import BeetsPlugin

if TYPE_CHECKING:
    import optparse

    from beets.library import Library


class FreedesktopPlugin(BeetsPlugin):
    def commands(self) -> list[ui.Subcommand]:
        deprecated = ui.Subcommand(
            "freedesktop",
            help="Print a message to redirect to thumbnails --dolphin",
        )
        deprecated.func = self.deprecation_message
        return [deprecated]

    def deprecation_message(
        self, lib: Library, opts: optparse.Values, args: list[str]
    ) -> None:
        ui.print_(
            "This plugin is deprecated. Its functionality is "
            "superseded by the 'thumbnails' plugin"
        )
        ui.print_(
            "'thumbnails --dolphin' replaces freedesktop. See doc & "
            "changelog for more information"
        )
