"""The `write` command: write tag information to files."""

import os

from beets import library, logging, ui
from beets.util import syspath

from ._utils import do_query

# Global logger.
log = logging.getLogger("beets")


def write_items(lib, query, pretend, force):
    """Write tag information from the database to the respective files
    in the filesystem.
    """
    items, albums = do_query(lib, query, False, False)

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


def write_func(lib, opts, args):
    write_items(lib, args, opts.pretend, opts.force)


write_cmd = ui.Subcommand("write", help="write tag information to files")
write_cmd.parser.add_option(
    "-p",
    "--pretend",
    action="store_true",
    help="show all changes but do nothing",
)
write_cmd.parser.add_option(
    "-f",
    "--force",
    action="store_true",
    help="write tags even if the existing tags match the database",
)
write_cmd.func = write_func
