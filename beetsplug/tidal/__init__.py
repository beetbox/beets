from __future__ import annotations

import os
from functools import cached_property
from typing import TYPE_CHECKING

import confuse

from beets import ui
from beets.metadata_plugins import MetadataSourcePlugin

from .api import TidalAPI, TidalSession
from .authenticate import ui_auth_flow

if TYPE_CHECKING:
    import optparse
    from collections.abc import Iterable, Sequence

    from beets.autotag.hooks import AlbumInfo, TrackInfo
    from beets.library.models import Item, Library


class TidalPlugin(MetadataSourcePlugin):
    """Tidal metadata plugin.

    Allows to fetch metadata candidates from tidal.
    """

    def __init__(self) -> None:
        super().__init__()

        self.config.add(
            {
                "client_id": "mcjmpl1bPATJXcBT",
                "tokenfile": "tidal_token.json",
            }
        )
        self.config["client_id"].redact = True

        # We need to be authenticated if plugin is used to fetch metadata
        # otherwise the import cannot run.
        self.register_listener("import_begin", self.require_authentication)

    @cached_property
    def api(self) -> TidalAPI:
        return TidalAPI(
            TidalSession(
                client_id=self.config["client_id"].as_str(),
                token_path=self._tokenfile(),
            )
        )

    def _tokenfile(self) -> str:
        """Creates the token file if it doesn't exist"""
        return self.config["tokenfile"].get(confuse.Filename(in_app_dir=True))

    def require_authentication(self):
        if not os.path.isfile(self._tokenfile()):
            raise ui.UserError(
                "Please login to TIDAL"
                " using `beets tidal --auth` or disable tidal plugin"
            )

    def commands(self) -> list[ui.Subcommand]:
        tidal_cmd = ui.Subcommand(
            "tidal", help="Tidal metadata plugin commands"
        )
        tidal_cmd.parser.add_option(
            "-a",
            "--auth",
            action="store_true",
            help="Authenticate and login to Tidal",
            default=False,
        )

        def func(lib: Library, opts: optparse.Values, args: list[str]):
            if opts.auth:
                token = ui_auth_flow(self.config["client_id"].as_str())
                token.save_to(self._tokenfile())
                ui.print_(f"Saved tidal token in {self._tokenfile()}")
            else:
                tidal_cmd.print_help()

        tidal_cmd.func = func

        return [tidal_cmd]

    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        if not (tidal_id := self._extract_id(album_id)):
            return None
        print(tidal_id)
        breakpoint()

    def track_for_id(self, track_id: str) -> TrackInfo | None:
        if not (tidal_id := self._extract_id(track_id)):
            return None
        print(tidal_id)
        breakpoint()

    def candidates(
        self, items: Sequence[Item], artist: str, album: str, va_likely: bool
    ) -> Iterable[AlbumInfo]:
        breakpoint()
        return []

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterable[TrackInfo]:
        breakpoint()
        return []
