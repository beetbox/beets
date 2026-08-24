"""The 'move' command: Move/copy files to the library or a new base directory."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol

from typing_extensions import TypeIs

from beets import logging, ui
from beets.exceptions import UserError
from beets.util import MoveOperation, displayable_path, normpath, syspath
from beets.util.diff import colordiff

from .utils import do_query

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from beets.library import Album, Item, Library

# Global logger.
log = logging.getLogger("beets")


class MoveCLIOpts(Protocol):
    album: bool
    copy: bool
    dest: str | None
    export: bool
    pretend: bool
    timid: bool


def show_path_changes(path_changes: Iterable[tuple[bytes, bytes]]) -> None:
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
    sources_bytes, destinations_bytes = zip(*path_changes)

    # Ensure unicode output
    sources = list(map(displayable_path, sources_bytes))
    destinations = list(map(displayable_path, destinations_bytes))

    # Calculate widths for terminal split
    col_width = (ui.term_width() - len(" -> ")) // 2
    max_width = len(max(sources + destinations, key=len))

    if max_width > col_width:
        # Print every change over two lines
        for source, dest in zip(sources, destinations):
            color_source, color_dest = colordiff(source, dest)
            ui.print_(f"{color_source} \n  -> {color_dest}")
    else:
        # Print every change on a single line, and add a header
        title_pad = max_width - len("Source ") + len(" -> ")

        ui.print_(f"Source {' ' * title_pad} Destination")
        for source, dest in zip(sources, destinations):
            pad = max_width - len(source)
            color_source, color_dest = colordiff(source, dest)
            ui.print_(f"{color_source} {' ' * pad} -> {color_dest}")


def is_album_selection(
    objects: list[Item] | list[Album], album: bool
) -> TypeIs[list[Album]]:
    return album


def move_items(
    lib: Library,
    dest: bytes | None,
    query: Sequence[str],
    copy: bool,
    album: bool,
    pretend: bool,
    confirm: bool = False,
    export: bool = False,
) -> None:
    """Moves or copies items to a new base directory, given by dest. If
    dest is None, then the library's base directory is used, making the
    command "consolidate" files.
    """
    items, albums = do_query(lib, query, album, False)
    objs = albums if album else items
    num_objs = len(objs)

    # Filter out files that don't need to be moved.
    def isitemmoved(item: Item) -> bool:
        return item.path != item.destination(basedir=dest)

    def isalbummoved(album: Album) -> bool:
        return any(isitemmoved(i) for i in album.items())

    if is_album_selection(objs, album):
        objs = list(filter(isalbummoved, objs))
    else:
        objs = list(filter(isitemmoved, objs))

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
        if is_album_selection(objs, album):
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


def move_func(lib: Library, opts: MoveCLIOpts, args: list[str]) -> None:
    dest = normpath(opts.dest) if opts.dest else None
    if dest is not None:
        if not os.path.isdir(syspath(dest)):
            raise UserError(f"no such directory: {displayable_path(dest)}")

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
    default=False,
    action="store_true",
    help="always confirm all actions",
)
move_cmd.parser.add_option(
    "-e",
    "--export",
    action="store_true",
    default=False,
    help="copy without changing the database path",
)
move_cmd.parser.add_album_option()
move_cmd.func = move_func
