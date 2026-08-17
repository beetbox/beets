"""Utility functions for beets UI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from beets.exceptions import UserError

if TYPE_CHECKING:
    from beets.library import Album, Item, Library


def do_query(
    lib: Library, query: list[str], album: bool, also_items: bool = True
) -> tuple[list[Item], list[Album]]:
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
    if not album and not items:
        raise UserError("No matching items found.")

    return items, albums
