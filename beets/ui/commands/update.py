"""The `update` command: Update library contents according to on-disk tags."""

import os

from beets import library, logging
from beets.ui.colors import colorize
from beets.ui.core import (
    Subcommand,
    input_yn,
    print_,
    should_move,
    show_model_changes,
)
from beets.util import ancestry, syspath

from ._utils import do_query

# Global logger.
log = logging.getLogger("beets")


def update_items(lib, query, album, move, pretend, fields, exclude_fields=None):
    """For all the items matched by the query, update the library to
    reflect the item's embedded tags.
    :param fields: The fields to be stored. If not specified, all fields will
    be.
    :param exclude_fields: The fields to not be stored. If not specified, all
    fields will be.
    """
    with lib.transaction():
        items, _ = do_query(lib, query, album)
        if move and fields is not None and "path" not in fields:
            # Special case: if an item needs to be moved, the path field has to
            # updated; otherwise the new path will not be reflected in the
            # database.
            fields.append("path")
        if fields is None:
            # no fields were provided, update all media fields
            item_fields = fields or library.Item._media_fields
            if move and "path" not in item_fields:
                # move is enabled, add 'path' to the list of fields to update
                item_fields.add("path")
        else:
            # fields was provided, just update those
            item_fields = fields
        # get all the album fields to update
        album_fields = fields or library.Album._fields.keys()
        if exclude_fields:
            # remove any excluded fields from the item and album sets
            item_fields = [f for f in item_fields if f not in exclude_fields]
            album_fields = [f for f in album_fields if f not in exclude_fields]

        # Walk through the items and pick up their changes.
        affected_albums = set()
        for item in items:
            # Item deleted?
            if not item.path or not os.path.exists(syspath(item.path)):
                print_(format(item))
                print_(colorize("text_error", "  deleted"))
                if not pretend:
                    item.remove(True)
                affected_albums.add(item.album_id)
                continue

            # Did the item change since last checked?
            if item.current_mtime() <= item.mtime:
                log.debug(
                    "skipping {0.filepath} because mtime is up to date ({0.mtime})",
                    item,
                )
                continue

            # Read new data.
            try:
                item.read()
            except library.ReadError as exc:
                log.error("error reading {.filepath}: {}", item, exc)
                continue

            # Special-case album artist when it matches track artist. (Hacky
            # but necessary for preserving album-level metadata for non-
            # autotagged imports.)
            if not item.albumartist:
                old_item = lib.get_item(item.id)
                if old_item.albumartist == old_item.artist == item.artist:
                    item.albumartist = old_item.albumartist
                    item._dirty.discard("albumartist")

            # Check for and display changes.
            changed = show_model_changes(item, fields=item_fields)

            # Save changes.
            if not pretend:
                if changed:
                    # Move the item if it's in the library.
                    if move and lib.directory in ancestry(item.path):
                        item.move(store=False)

                    item.store(fields=item_fields)
                    affected_albums.add(item.album_id)
                else:
                    # The file's mtime was different, but there were no
                    # changes to the metadata. Store the new mtime,
                    # which is set in the call to read(), so we don't
                    # check this again in the future.
                    item.store(fields=item_fields)

        # Skip album changes while pretending.
        if pretend:
            return

        # Modify affected albums to reflect changes in their items.
        for album_id in affected_albums:
            if album_id is None:  # Singletons.
                continue
            album = lib.get_album(album_id)
            if not album:  # Empty albums have already been removed.
                log.debug("emptied album {}", album_id)
                continue
            first_item = album.items().get()

            # Update album structure to reflect an item in it.
            for key in library.Album.item_keys:
                album[key] = first_item[key]
            album.store(fields=album_fields)

            # Move album art (and any inconsistent items).
            if move and lib.directory in ancestry(first_item.path):
                log.debug("moving album {}", album_id)

                # Manually moving and storing the album.
                items = list(album.items())
                for item in items:
                    item.move(store=False, with_album=False)
                    item.store(fields=item_fields)
                album.move(store=False)
                album.store(fields=album_fields)


def update_func(lib, opts, args):
    # Verify that the library folder exists to prevent accidental wipes.
    if not os.path.isdir(syspath(lib.directory)):
        print_("Library path is unavailable or does not exist.")
        print_(lib.directory)
        if not input_yn("Are you sure you want to continue (y/n)?", True):
            return
    update_items(
        lib,
        args,
        opts.album,
        should_move(opts.move),
        opts.pretend,
        opts.fields,
        opts.exclude_fields,
    )


update_cmd = Subcommand(
    "update",
    help="update the library",
    aliases=(
        "upd",
        "up",
    ),
)
update_cmd.parser.add_album_option()
update_cmd.parser.add_format_option()
update_cmd.parser.add_option(
    "-m",
    "--move",
    action="store_true",
    dest="move",
    help="move files in the library directory",
)
update_cmd.parser.add_option(
    "-M",
    "--nomove",
    action="store_false",
    dest="move",
    help="don't move files in library",
)
update_cmd.parser.add_option(
    "-p",
    "--pretend",
    action="store_true",
    help="show all changes but do nothing",
)
update_cmd.parser.add_option(
    "-F",
    "--field",
    default=None,
    action="append",
    dest="fields",
    help="list of fields to update",
)
update_cmd.parser.add_option(
    "-e",
    "--exclude-field",
    default=None,
    action="append",
    dest="exclude_fields",
    help="list of fields to exclude from updates",
)
update_cmd.func = update_func
