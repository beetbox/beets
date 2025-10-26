"""Utility functions for beets UI commands."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from beets.ui._common import UserError
from beets.util import PathLike, displayable_path, normpath, syspath

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from _typeshed import FileDescriptorOrPath


def do_query(lib, query, album, also_items=True):
    """For commands that operate on matched items, performs a query
    and returns a list of matching items and a list of matching
    albums. (The latter is only nonempty when album is True.) Raises
    a UserError if no items match. also_items controls whether, when
    fetching albums, the associated items should be fetched also.
    """
    if album:
        albums = list(lib.albums(query))
        items = []
        if also_items:
            for al in albums:
                items += al.items()

    else:
        albums = []
        items = list(lib.items(query))

    if album and not albums:
        raise UserError("No matching albums found.")
    elif not album and not items:
        raise UserError("No matching items found.")

    return items, albums


def paths_from_logfile(path: FileDescriptorOrPath) -> Iterator[str]:
    """Parse the logfile and yield skipped paths to pass to the `import`
    command.
    """
    with open(path, encoding="utf-8") as fp:
        i: int
        line: str
        for i, line in enumerate(fp, start=1):
            verb: str
            sep: str
            paths: str
            verb, sep, paths = line.rstrip("\n").partition(" ")
            if not sep:
                raise ValueError(f"line {i} is invalid")

            # Ignore informational lines that don't need to be re-imported.
            if verb in {"import", "duplicate-keep", "duplicate-replace"}:
                continue

            if verb not in {"asis", "skip", "duplicate-skip"}:
                raise ValueError(f"line {i} contains unknown verb {verb}")

            yield os.path.commonpath(paths.split("; "))


def parse_logfiles(logfiles: Iterable[PathLike]) -> Iterator[str]:
    """Parse all `logfiles` and yield paths from it."""
    logfile: PathLike
    for logfile in logfiles:
        try:
            yield from paths_from_logfile(syspath(normpath(logfile)))
        except ValueError as err:
            raise UserError(
                f"malformed logfile {displayable_path(logfile)}: {err}"
            ) from err
        except OSError as err:
            raise UserError(
                f"unreadable logfile {displayable_path(logfile)}: {err}"
            ) from err
