"""The 'move' command: Move/copy files to the library or a new base directory."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from beets import logging, ui
from beets.util import MoveOperation, displayable_path, normpath, syspath

from .utils import do_query

if TYPE_CHECKING:
    from beets.util import PathLike

# Global logger.
log = logging.getLogger("beets")


def show_path_changes(path_changes):
    """Given a list of tuples (source, destination) that indicate the
    path changes, log the changes as INFO-level output to the beets log.
    The output is guaranteed to be unicode.

    Every pair is shown on a single line if the terminal width permits it,
    else it is split over two lines. E.g.,

    Source -> Destination

    vs.

    Source
      -> Destination
    """
    sources, destinations = zip(*path_changes)

    # Ensure unicode output
    sources = list(map(displayable_path, sources))
    destinations = list(map(displayable_path, destinations))

    # Calculate widths for terminal split
    col_width = (ui.term_width() - len(" -> ")) // 2
    max_width = len(max(sources + destinations, key=len))

    if max_width > col_width:
        # Print every change over two lines
        for source, dest in zip(sources, destinations):
            color_source, color_dest = ui.colordiff(source, dest)
            ui.print_(f"{color_source} \n  -> {color_dest}")
    else:
        # Print every change on a single line, and add a header
        title_pad = max_width - len("Source ") + len(" -> ")

        ui.print_(f"Source {' ' * title_pad} Destination")
        for source, dest in zip(sources, destinations):
            pad = max_width - len(source)
            color_source, color_dest = ui.colordiff(source, dest)
            ui.print_(f"{color_source} {' ' * pad} -> {color_dest}")


def move_items(
    lib,
    dest_path: PathLike,
    query,
    copy,
    album,
    pretend,
    confirm=False,
    export=False,
):
    """Moves or copies items to a new base directory, given by dest. If
    dest is None, then the library's base directory is used, making the
    command "consolidate" files.
    """
    dest = os.fsencode(dest_path) if dest_path else dest_path
    items, albums = do_query(lib, query, album, False)
    objs = albums if album else items
    num_objs = len(objs)

    # Filter out files that don't need to be moved.
    def isitemmoved(item):
        return item.path != item.destination(basedir=dest)

    def isalbummoved(album):
        return any(isitemmoved(i) for i in album.items())

    objs = [o for o in objs if (isalbummoved if album else isitemmoved)(o)]
    num_unmoved = num_objs - len(objs)
    # Report unmoved files that match the query.
    unmoved_msg = ""
    if num_unmoved > 0:
        unmoved_msg = f" ({num_unmoved} already in place)"

    copy = copy or export  # Exporting always copies.
    action = "Copying" if copy else "Moving"
    act = "copy" if copy else "move"
    entity = "album" if album else "item"
    log.info(
        "{} {} {}{}{}.",
        action,
        len(objs),
        entity,
        "s" if len(objs) != 1 else "",
        unmoved_msg,
    )
    if not objs:
        return

    if pretend:
        if album:
            show_path_changes(
                [
                    (item.path, item.destination(basedir=dest))
                    for obj in objs
                    for item in obj.items()
                ]
            )
        else:
            show_path_changes(
                [(obj.path, obj.destination(basedir=dest)) for obj in objs]
            )
    else:
        if confirm:
            objs = ui.input_select_objects(
                f"Really {act}",
                objs,
                lambda o: show_path_changes(
                    [(o.path, o.destination(basedir=dest))]
                ),
            )

        for obj in objs:
            log.debug("moving: {.filepath}", obj)

            if export:
                # Copy without affecting the database.
                obj.move(
                    operation=MoveOperation.COPY, basedir=dest, store=False
                )
            else:
                # Ordinary move/copy: store the new path.
                if copy:
                    obj.move(operation=MoveOperation.COPY, basedir=dest)
                else:
                    obj.move(operation=MoveOperation.MOVE, basedir=dest)


def move_func(lib, opts, args):
    dest = opts.dest
    if dest is not None:
        dest = normpath(dest)
        if not os.path.isdir(syspath(dest)):
            raise ui.UserError(f"no such directory: {displayable_path(dest)}")

    move_items(
        lib,
        dest,
        args,
        opts.copy,
        opts.album,
        opts.pretend,
        opts.timid,
        opts.export,
    )


move_cmd = ui.Subcommand("move", help="move or copy items", aliases=("mv",))
move_cmd.parser.add_option(
    "-d", "--dest", metavar="DIR", dest="dest", help="destination directory"
)
move_cmd.parser.add_option(
    "-c",
    "--copy",
    default=False,
    action="store_true",
    help="copy instead of moving",
)
move_cmd.parser.add_option(
    "-p",
    "--pretend",
    default=False,
    action="store_true",
    help="show how files would be moved, but don't touch anything",
)
move_cmd.parser.add_option(
    "-t",
    "--timid",
    dest="timid",
    action="store_true",
    help="always confirm all actions",
)
move_cmd.parser.add_option(
    "-e",
    "--export",
    default=False,
    action="store_true",
    help="copy without changing the database path",
)
move_cmd.parser.add_album_option()
move_cmd.func = move_func
