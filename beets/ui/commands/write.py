"""The `write` command: write tag information to files."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol

from beets import library, logging, ui
from beets.exceptions import UserError
from beets.util import syspath

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.library import Library


# Global logger.
log = logging.getLogger("beets")


class WriteCLIOpts(Protocol):
    force: bool
    pretend: bool


def write_items(
    lib: Library, query: Sequence[str], pretend: bool, force: bool
) -> None:
    """Write tag information from the database to the respective files
    in the filesystem.
    """
    items = lib.items(query)

    if not items:
        raise UserError("No matching items to write.")

    for item in items:
        # Item deleted?
        if not os.path.exists(syspath(item.path)):
            log.info("missing file: {.filepath}", item)
            continue

        # Get an Item object reflecting the "clean" (on-disk) state.
        try:
            clean_item = library.Item.from_path(item.path)
        except library.ReadError as exc:
            log.error("error reading {.filepath}: {}", item, exc)
            continue

        # Check for and display changes.
        changed = ui.show_model_changes(
            item, clean_item, library.Item._media_tag_fields, force
        )
        if (changed or force) and not pretend:
            # We use `try_sync` here to keep the mtime up to date in the
            # database.
            item.try_sync(True, False)


def write_func(lib: Library, opts: WriteCLIOpts, args: list[str]) -> None:
    write_items(lib, args, opts.pretend, opts.force)


write_cmd = ui.Subcommand("write", help="write tag information to files")
write_cmd.parser.add_option(
    "-p",
    "--pretend",
    action="store_true",
    default=False,
    help="show all changes but do nothing",
)
write_cmd.parser.add_option(
    "-f",
    "--force",
    action="store_true",
    default=False,
    help="write tags even if the existing tags match the database",
)
write_cmd.func = write_func
