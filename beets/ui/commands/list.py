"""The 'list' command: query and show library contents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from beets import ui
from beets.exceptions import UserError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.library import Library


class ListCLIOpts(Protocol):
    album: bool
    limit: int | None


def list_items(
    lib: Library, query: Sequence[str], opts: ListCLIOpts, fmt: str = ""
) -> None:
    """Print out items in lib matching query. If album, then search for
    albums instead of single items.
    """
    if opts.album:
        for _album in lib.albums(query, limit=opts.limit):
            ui.print_(format(_album, fmt))
    else:
        for item in lib.items(query, limit=opts.limit):
            ui.print_(format(item, fmt))


def list_func(lib: Library, opts: ListCLIOpts, args: list[str]) -> None:
    if opts.limit is not None and opts.limit < 0:
        raise UserError("-l / --limit argument must be a non-negative integer")
    list_items(lib, args, opts)


list_cmd = ui.Subcommand("list", help="query the library", aliases=("ls",))
list_cmd.parser.set_usage(
    list_cmd.parser.get_usage().rstrip()
    + "\nExample: %prog -f '$album: $title' artist:beatles"
)
list_cmd.parser.add_all_common_options()
list_cmd.parser.add_option(
    "-l", "--limit", type=int, help="limit query results"
)
list_cmd.func = list_func
