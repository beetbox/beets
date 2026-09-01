"""The `remove` command: remove items from the library (and optionally delete files)."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Protocol

from beets import ui
from beets.exceptions import UserError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from beets.library import Album, AlbumOrItem, Item, Library


class RemoveCLIOpts(Protocol):
    album: bool
    delete: bool
    force: bool


def remove_objects(
    objs: Sequence[AlbumOrItem],
    fmt_obj: Callable[[str, AlbumOrItem], None],
    file_count: int,
    album_str: str,
    lib: Library,
    opts: RemoveCLIOpts,
) -> None:
    # Confirm file removal if not forcing removal.
    if not objs:
        raise UserError("No matching objects to remove.")

    if opts.force:
        selected_objs = objs
    else:
        file_suffix = "s" if file_count > 1 else ""
        if opts.delete:
            fmt = "$path - $title"
            prompt = "Really DELETE"
            prompt_all = (
                f"Really DELETE {file_count} file{file_suffix}{album_str}"
            )
        else:
            fmt = ""
            prompt = "Really remove from the library?"
            prompt_all = (
                f"Really remove {file_count} item{file_suffix}{album_str} "
                "from the library?"
            )

        _fmt = partial(fmt_obj, fmt)

        # Show all the items.
        for o in objs:
            _fmt(o)

        # Confirm with user.
        selected_objs = ui.input_select_objects(
            prompt, objs, _fmt, prompt_all=prompt_all
        )

    if not selected_objs:
        return

    # Remove (and possibly delete) items.
    with lib.transaction():
        for obj in selected_objs:
            obj.remove(opts.delete)


def fmt_item(fmt: str, t: Item) -> None:
    ui.print_(format(t, fmt))


def fmt_album(fmt: str, a: Album) -> None:
    ui.print_()
    for i in a.items():
        fmt_item(fmt, i)


def remove_items(
    lib: Library, query: Sequence[str], opts: RemoveCLIOpts
) -> None:
    """Remove items matching query from lib."""
    items = list(lib.items(query))
    album_str = ""

    remove_objects(items, fmt_item, len(items), album_str, lib, opts=opts)


def remove_albums(
    lib: Library, query: Sequence[str], opts: RemoveCLIOpts
) -> None:
    """Remove albums matching query from lib."""
    albums = list(lib.albums(query))
    items = [i for a in albums for i in a.items()]
    album_str = f" and {len(albums)} album{'s' if len(albums) > 1 else ''}"

    remove_objects(albums, fmt_album, len(items), album_str, lib, opts=opts)


def remove_func(lib: Library, opts: RemoveCLIOpts, args: list[str]) -> None:
    method = remove_albums if opts.album else remove_items
    method(lib, args, opts=opts)


remove_cmd = ui.Subcommand(
    "remove", help="remove matching items from the library", aliases=("rm",)
)
remove_cmd.parser.add_option(
    "-d",
    "--delete",
    action="store_true",
    default=False,
    help="also remove files from disk",
)
remove_cmd.parser.add_option(
    "-f",
    "--force",
    action="store_true",
    default=False,
    help="do not ask when removing items",
)
remove_cmd.parser.add_album_option()
remove_cmd.func = remove_func
