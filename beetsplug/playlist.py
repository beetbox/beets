from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal

import confuse

import beets
from beets import util
from beets.dbcore.query import InQuery
from beets.plugins import BeetsPlugin
from beets.util import path_as_posix

if TYPE_CHECKING:
    from collections.abc import Iterator

    from confuse import ConfigView

    from beets.dbcore.query import FieldQueryType
    from beets.library import Item, Library


def is_m3u_file(path: Path) -> bool:
    return path.suffix.lower() in {".m3u", ".m3u8"}


class PlaylistMixin:
    @staticmethod
    def _get_playlist_dir(config: ConfigView) -> Path:
        return config["playlist_dir"].as_path()

    @staticmethod
    def _get_relative_to(config: ConfigView) -> Path | None:
        relative_to_val: Literal["library", "playlist"] | Path = config[
            "relative_to"
        ].get(
            confuse.OneOf(
                [confuse.Choice(["library", "playlist"]), confuse.Path()]
            )
        )
        if relative_to_val == "playlist":
            return None

        if relative_to_val == "library":
            relative_to = beets.config["directory"].as_path()
        else:
            relative_to = relative_to_val

        return util.normpath(relative_to)


class PlaylistQuery(PlaylistMixin, InQuery[bytes]):
    """Matches files listed by a playlist file."""

    @util.cached_classproperty
    def relative_to(cls) -> Path | None:
        return cls._get_relative_to(beets.config["playlist"])

    @util.cached_classproperty
    def playlist_dir(cls) -> Path:
        return cls._get_playlist_dir(beets.config["playlist"])

    @staticmethod
    def read_paths(playlist_path: Path, relative_to: Path | None) -> list[Path]:
        relative_to = relative_to or playlist_path.parent
        return [
            util.normpath(relative_to / os.fsdecode(ln))
            for ln in playlist_path.read_bytes().splitlines()
            if ln and not ln.startswith(b"#")
        ]

    def __init__(self, _, pattern: str, __) -> None:
        # Get the full path to the playlist
        playlist_paths = (Path(pattern), self.playlist_dir / f"{pattern}.m3u")

        relative_to_config = self.relative_to
        paths = []
        # Filter only M3U playlist
        for playlist_path in filter(is_m3u_file, playlist_paths):
            with suppress(OSError):
                paths = self.read_paths(playlist_path, relative_to_config)
                break
        super().__init__("path", list(map(os.fsencode, paths)))


class PlaylistPlugin(PlaylistMixin, BeetsPlugin):
    item_queries: ClassVar[dict[str, FieldQueryType]] = {
        "playlist": PlaylistQuery
    }

    changes: dict[bytes, bytes | None]

    def __init__(self) -> None:
        super().__init__()
        self.config.add(
            {
                "auto": False,
                "playlist_dir": ".",
                "relative_to": "library",
                "forward_slash": False,
            }
        )

        self.changes = {}

        if self.config["auto"]:
            self.register_listener("item_moved", self.item_moved)
            self.register_listener("item_removed", self.item_removed)
            self.register_listener("cli_exit", self.cli_exit)

    @cached_property
    def playlist_dir(self) -> Path:
        return self._get_playlist_dir(self.config)

    @cached_property
    def relative_to(self) -> Path | None:
        return self._get_relative_to(self.config)

    def item_moved(self, item: Item, source: bytes, destination: bytes) -> None:
        self.changes[source] = destination

    def item_removed(self, item: Item) -> None:
        if not os.path.exists(beets.util.syspath(item.path)):
            self.changes[item.path] = None

    def cli_exit(self, lib: Library) -> None:
        for playlist in self.find_playlists():
            self._log.info("Updating playlist: {}", playlist)
            base_dir = beets.util.bytestring_path(
                self.relative_to
                if self.relative_to
                else os.path.dirname(playlist)
            )

            try:
                self.update_playlist(playlist, base_dir)
            except beets.util.FilesystemError:
                self._log.error("Failed to update playlist: {}", playlist)

    def find_playlists(self) -> Iterator[Path]:
        """Find M3U playlists in the playlist directory."""
        try:
            yield from filter(is_m3u_file, self.playlist_dir.iterdir())
        except OSError:
            self._log.warning(
                "Unable to open playlist directory {.playlist_dir}", self
            )
            return

    def update_playlist(self, filename: Path, base_dir: bytes) -> None:
        """Find M3U playlists in the specified directory."""
        changes = 0
        deletions = 0

        with tempfile.NamedTemporaryFile(mode="w+b", delete=False) as tempfp:
            new_playlist = tempfp.name
            with open(filename, mode="rb") as fp:
                for line in fp:
                    original_path = line.rstrip(b"\r\n")

                    # Ensure that path from playlist is absolute
                    is_relative = not os.path.isabs(line)
                    if is_relative:
                        lookup = os.path.join(base_dir, original_path)
                    else:
                        lookup = original_path

                    try:
                        new_path = self.changes[beets.util.normpath(lookup)]
                    except KeyError:
                        if self.config["forward_slash"]:
                            line = path_as_posix(line)
                        tempfp.write(line)
                    else:
                        if new_path is None:
                            # Item has been deleted
                            deletions += 1
                            continue

                        changes += 1
                        if is_relative:
                            new_path = os.path.relpath(new_path, base_dir)
                        line = line.replace(original_path, new_path)
                        if self.config["forward_slash"]:
                            line = path_as_posix(line)
                        tempfp.write(line)

        if changes or deletions:
            self._log.info(
                "Updated playlist {} ({} changes, {} deletions)",
                filename,
                changes,
                deletions,
            )
            beets.util.copy(new_playlist, filename, replace=True)
        beets.util.remove(new_playlist)
