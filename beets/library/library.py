from __future__ import annotations

from typing import TYPE_CHECKING

import platformdirs

import beets
from beets import dbcore
from beets.util import normpath

from .models import Album, Item
from .queries import PF_KEY_DEFAULT, parse_query_parts, parse_query_string

if TYPE_CHECKING:
    from beets.dbcore import Results


class Library(dbcore.Database):
    """A database of music containing songs and albums."""

    _models = (Item, Album)

    def __init__(
        self,
        path="library.blb",
        directory: str | None = None,
        path_formats=((PF_KEY_DEFAULT, "$artist/$album/$track $title"),),
        replacements=None,
    ):
        timeout = beets.config["timeout"].as_number()
        super().__init__(path, timeout=timeout)

        self.directory = normpath(directory or platformdirs.user_music_path())

        self.path_formats = path_formats
        self.replacements = replacements

        # Used for template substitution performance.
        self._memotable: dict[tuple[str, ...], str] = {}

    # Adding objects to the database.

    def add(self, obj):
        """Add the :class:`Item` or :class:`Album` object to the library
        database.

        Return the object's new id.
        """
        obj.add(self)
        self._memotable = {}
        return obj.id

    def add_album(self, items):
        """Create a new album consisting of a list of items.

        The items are added to the database if they don't yet have an
        ID. Return a new :class:`Album` object. The list items must not
        be empty.
        """
        if not items:
            raise ValueError("need at least one item")

        # Create the album structure using metadata from the first item.
        values = {key: items[0][key] for key in Album.item_keys}
        album = Album(self, **values)

        # Add the album structure and set the items' album_id fields.
        # Store or add the items.
        with self.transaction():
            album.add(self)
            for item in items:
                item.album_id = album.id
                if item.id is None:
                    item.add(self)
                else:
                    item.store()

        return album

    # Querying.

    def _fetch(self, model_cls, query, sort=None):
        """Parse a query and fetch.

        If an order specification is present in the query string
        the `sort` argument is ignored.
        """
        # Parse the query, if necessary.
        try:
            parsed_sort = None
            if isinstance(query, str):
                query, parsed_sort = parse_query_string(query, model_cls)
            elif isinstance(query, (list, tuple)):
                query, parsed_sort = parse_query_parts(query, model_cls)
        except dbcore.query.InvalidQueryArgumentValueError as exc:
            raise dbcore.InvalidQueryError(query, exc)

        # Any non-null sort specified by the parsed query overrides the
        # provided sort.
        if parsed_sort and not isinstance(parsed_sort, dbcore.query.NullSort):
            sort = parsed_sort

        return super()._fetch(model_cls, query, sort)

    @staticmethod
    def get_default_album_sort():
        """Get a :class:`Sort` object for albums from the config option."""
        return dbcore.sort_from_strings(
            Album, beets.config["sort_album"].as_str_seq()
        )

    @staticmethod
    def get_default_item_sort():
        """Get a :class:`Sort` object for items from the config option."""
        return dbcore.sort_from_strings(
            Item, beets.config["sort_item"].as_str_seq()
        )

    def albums(self, query=None, sort=None) -> Results[Album]:
        """Get :class:`Album` objects matching the query."""
        return self._fetch(Album, query, sort or self.get_default_album_sort())

    def items(self, query=None, sort=None) -> Results[Item]:
        """Get :class:`Item` objects matching the query."""
        return self._fetch(Item, query, sort or self.get_default_item_sort())

    # Convenience accessors.
    def get_item(self, id_: int) -> Item | None:
        """Fetch a :class:`Item` by its ID.

        Return `None` if no match is found.
        """
        return self._get(Item, id_)

    def get_album(self, item_or_id: Item | int) -> Album | None:
        """Given an album ID or an item associated with an album, return
        a :class:`Album` object for the album.

        If no such album exists, return `None`.
        """
        album_id = (
            item_or_id if isinstance(item_or_id, int) else item_or_id.album_id
        )
        return self._get(Album, album_id) if album_id else None
