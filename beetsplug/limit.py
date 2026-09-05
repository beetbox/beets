"""Adds head/tail functionality to list/ls.

1. Implemented as `lslimit` command with `--head` and `--tail` options. This is
   the idiomatic way to use this plugin.
2. Implemented as query prefix `<` for head functionality only. This is the
   composable way to use the plugin (plays nicely with anything that uses the
   query language).
"""

from __future__ import annotations

from collections import deque
from itertools import islice
from typing import TYPE_CHECKING, Protocol

from beets.dbcore import FieldQuery
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, print_

if TYPE_CHECKING:
    from collections.abc import Iterable

    from beets.library import LibModel, Library

    from ._typing import JSONDict


class LsLimitCLIOpts(Protocol):
    album: bool
    head: int | None
    tail: int | None


def lslimit(lib: Library, opts: LsLimitCLIOpts, args: list[str]) -> None:
    """Query command with head/tail."""

    if (opts.head is not None) and (opts.tail is not None):
        raise ValueError("Only use one of --head and --tail")
    if (opts.head or opts.tail or 0) < 0:
        raise ValueError("Limit value must be non-negative")

    objs: Iterable[LibModel]
    if opts.album:
        objs = lib.albums(args)
    else:
        objs = lib.items(args)

    if opts.head is not None:
        objs = islice(objs, opts.head)
    elif opts.tail is not None:
        objs = deque(objs, opts.tail)

    for obj in objs:
        print_(format(obj))


lslimit_cmd = Subcommand("lslimit", help="query with optional head or tail")

lslimit_cmd.parser.add_option(
    "--head", action="store", type="int", default=None
)

lslimit_cmd.parser.add_option(
    "--tail", action="store", type="int", default=None
)

lslimit_cmd.parser.add_all_common_options()
lslimit_cmd.func = lslimit


class LimitPlugin(BeetsPlugin):
    """Query limit functionality via command and query prefix."""

    def commands(self) -> list[Subcommand]:
        """Expose `lslimit` subcommand."""
        return [lslimit_cmd]

    def queries(self) -> JSONDict:
        class HeadQuery(FieldQuery):
            """This inner class pattern allows the query to track state."""

            n = 0
            N = None

            def __init__(self, *args, **kwargs) -> None:
                """Force the query to be slow so that 'value_match' is called."""
                super().__init__(*args, **kwargs)
                self.fast = False

            @classmethod
            def value_match(cls, pattern: str, value: str) -> bool:
                if cls.N is None:
                    cls.N = int(pattern)
                    if cls.N < 0:
                        raise ValueError("Limit value must be non-negative")
                cls.n += 1
                return cls.n <= cls.N

        return {"<": HeadQuery}
