"""Update library's tags using Beatport."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

from beets import library, ui, util
from beets.autotag import AlbumMatch, Distance, TrackMatch
from beets.plugins import BeetsPlugin, apply_item_changes
from beets.util.deprecation import deprecate_for_user

from .beatport import BeatportPlugin

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.library import Album, Item, Library


class BPSyncCLIOpts(Protocol):
    move: bool | None
    pretend: bool
    write: bool | None


class BPSyncPlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        deprecate_for_user(self._log, "The 'bpsync' plugin")
        self.beatport_plugin = BeatportPlugin()
        # this would cause an error but this plugin is dead
        self.beatport_plugin.setup()

    def commands(self) -> list[ui.Subcommand]:
        cmd = ui.Subcommand("bpsync", help="update metadata from Beatport")
        cmd.parser.add_option(
            "-p",
            "--pretend",
            action="store_true",
            default=False,
            help="show all changes but do nothing",
        )
        cmd.parser.add_option(
            "-m",
            "--move",
            action="store_true",
            dest="move",
            help="move files in the library directory",
        )
        cmd.parser.add_option(
            "-M",
            "--nomove",
            action="store_false",
            dest="move",
            help="don't move files in library",
        )
        cmd.parser.add_option(
            "-W",
            "--nowrite",
            action="store_false",
            default=None,
            dest="write",
            help="don't write updated metadata to files",
        )
        cmd.parser.add_format_option()
        cmd.func = self.func
        return [cmd]

    def func(self, lib: Library, opts: BPSyncCLIOpts, args: list[str]) -> None:
        """Command handler for the bpsync function."""
        move = ui.should_move(opts.move)
        pretend = opts.pretend
        write = ui.should_write(opts.write)

        self.singletons(lib, args, move, pretend, write)
        self.albums(lib, args, move, pretend, write)

    def singletons(
        self,
        lib: Library,
        query: Sequence[str],
        move: bool,
        pretend: bool,
        write: bool,
    ) -> None:
        """Retrieve and apply info from the autotagger for items matched by
        query.
        """
        for item in lib.items([*query, "singleton:true"]):
            if not item.mb_trackid:
                self._log.info(
                    "Skipping singleton with no mb_trackid: {}", item
                )
                continue

            if not self.is_beatport_track(item):
                self._log.info(
                    "Skipping non-{.beatport_plugin.data_source} singleton: {}",
                    self,
                    item,
                )
                continue

            # Apply.
            if trackinfo := self.beatport_plugin.track_for_id(item.mb_trackid):
                with lib.transaction():
                    TrackMatch(Distance(), trackinfo, item).apply_metadata(
                        from_scratch=False
                    )
                    apply_item_changes(lib, item, move, pretend, write)

    @staticmethod
    def is_beatport_track(item: Item) -> bool:
        return (
            item.get("data_source") == BeatportPlugin.data_source
            and item.mb_trackid.isnumeric()
        )

    def get_album_tracks(self, album: Album) -> list[Item] | Literal[False]:
        if not album.mb_albumid:
            self._log.info("Skipping album with no mb_albumid: {}", album)
            return False
        if not album.mb_albumid.isnumeric():
            self._log.info(
                "Skipping album with invalid {.beatport_plugin.data_source} ID: {}",
                self,
                album,
            )
            return False
        items = list(album.items())
        if album.get("data_source") == self.beatport_plugin.data_source:
            return items
        if not all(self.is_beatport_track(item) for item in items):
            self._log.info(
                "Skipping non-{.beatport_plugin.data_source} release: {}",
                self,
                album,
            )
            return False
        return items

    def albums(
        self,
        lib: Library,
        query: Sequence[str],
        move: bool,
        pretend: bool,
        write: bool,
    ) -> None:
        """Retrieve and apply info from the autotagger for albums matched by
        query and their items.
        """
        # Process matching albums.
        for album in lib.albums(query):
            # Do we have a valid Beatport album?
            items = self.get_album_tracks(album)
            if not items:
                continue

            # Get the Beatport album information.
            albuminfo = self.beatport_plugin.album_for_id(album.mb_albumid)
            if not albuminfo:
                self._log.info(
                    "Release ID {0.mb_albumid} not found for album {0}", album
                )
                continue

            beatport_trackid_to_trackinfo = {
                track.track_id: track for track in albuminfo.tracks
            }
            library_trackid_to_item = {item.mb_trackid: item for item in items}
            item_info_pairs = [
                (item, beatport_trackid_to_trackinfo[track_id])
                for track_id, item in library_trackid_to_item.items()
            ]

            self._log.info("applying changes to {}", album)
            with lib.transaction():
                AlbumMatch(
                    Distance(), albuminfo, dict(item_info_pairs)
                ).apply_metadata(from_scratch=False)
                changed = False
                # Find any changed item to apply Beatport changes to album.
                any_changed_item = items[0]
                for item in items:
                    item_changed = ui.show_model_changes(item)
                    changed |= item_changed
                    if item_changed:
                        any_changed_item = item
                        apply_item_changes(lib, item, move, pretend, write)

                if pretend or not changed:
                    continue

                # Update album structure to reflect an item in it.
                for key in library.Album.item_keys:
                    album[key] = any_changed_item[key]
                album.store()

                # Move album art (and any inconsistent items).
                if move and lib.directory in util.ancestry(items[0].path):
                    self._log.debug("moving album {}", album)
                    album.move()
