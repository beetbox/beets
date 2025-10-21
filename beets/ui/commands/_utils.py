"""Utility functions for beets UI commands."""

import os

from beets import ui
from beets.util import displayable_path, normpath, syspath


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
        raise ui.UserError("No matching albums found.")
    elif not album and not items:
        raise ui.UserError("No matching items found.")

    return items, albums


def paths_from_logfile(path):
    """Parse the logfile and yield skipped paths to pass to the `import`
    command.
    """
    with open(path, encoding="utf-8") as fp:
        for i, line in enumerate(fp, start=1):
            verb, sep, paths = line.rstrip("\n").partition(" ")
            if not sep:
                raise ValueError(f"line {i} is invalid")

            # Ignore informational lines that don't need to be re-imported.
            if verb in {"import", "duplicate-keep", "duplicate-replace"}:
                continue

            if verb not in {"asis", "skip", "duplicate-skip"}:
                raise ValueError(f"line {i} contains unknown verb {verb}")

            yield os.path.commonpath(paths.split("; "))


def parse_logfiles(logfiles):
    """Parse all `logfiles` and yield paths from it."""
    for logfile in logfiles:
        try:
            yield from paths_from_logfile(syspath(normpath(logfile)))
        except ValueError as err:
            raise ui.UserError(
                f"malformed logfile {displayable_path(logfile)}: {err}"
            ) from err
        except OSError as err:
            raise ui.UserError(
                f"unreadable logfile {displayable_path(logfile)}: {err}"
            ) from err
