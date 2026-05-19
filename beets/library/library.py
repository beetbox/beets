from __future__ import annotations

import re
from contextlib import contextmanager
from functools import cached_property
from typing import TYPE_CHECKING, TypeVar

import platformdirs

import beets
from beets import config, context, dbcore
from beets.exceptions import UserError
from beets.util import normpath
from beets.util.pathformats import get_path_formats

from . import migrations
from .models import Album, Item
from .queries import parse_query_parts, parse_query_string

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.dbcore import Results
    from beets.dbcore.query import Query, Sort
    from beets.util import Replacements
    from beets.util.pathformats import PathFormat

    from .models import LibModel

    LM = TypeVar("LM", bound=LibModel)


class Library(dbcore.Database):
    """A database of music containing songs and albums."""

    _models = (Item, Album)
    _migrations = (
        (migrations.MultiGenreFieldMigration, (Item, Album)),
        (migrations.LyricsMetadataInFlexFieldsMigration, (Item,)),
        (migrations.MultiRemixerFieldMigration, (Item,)),
        (migrations.MultiLyricistFieldMigration, (Item,)),
        (migrations.MultiComposerFieldMigration, (Item,)),
        (migrations.MultiArrangerFieldMigration, (Item,)),
        (migrations.RelativePathMigration, (Item, Album)),
        (migrations.RemoveInheritedArtpathMigration, (Item,)),
    )
    replacements: Replacements

    @cached_property
    def path_formats(self) -> list[PathFormat]:
        return get_path_formats(config["paths"])

    @staticmethod
    def get_replacements() -> Replacements:
        """Build regex/string replacement pairs from config."""
        replacements = []
        for pattern, repl in beets.config["replace"].get(dict).items():
            repl = repl or ""
            try:
                replacements.append((re.compile(pattern), repl))
            except re.error:
                raise UserError(
                    f"Malformed regular expression in replace: {pattern}"
                )
        return replacements

    def __init__(
        self,
        path="library.blb",
        directory: str | None = None,
        set_music_dir: bool = True,
    ):
        self.directory = normpath(directory or platformdirs.user_music_path())
        if set_music_dir:
            context.set_music_dir(self.directory)

        super().__init__(path, timeout=beets.config["timeout"].as_number())

        self.replacements = self.get_replacements()

        # Used for template substitution performance.
        self._memotable: dict[tuple[str, ...], str] = {}

    @contextmanager
    def music_dir_context(self):
        """Temporarily bind this library's directory to path conversion."""
        with context.music_dir(self.directory):
            yield self

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

    def _fetch(
        self,
        model_cls: type[LM],
        query: str | Sequence[str] | Query | None = None,
        sort: Sort | None = None,
    ) -> dbcore.Results[LM]:
        """Parse a query and fetch.

        If an order specification is present in the query string
        the `sort` argument is ignored.
        """
        # Parse the query, if necessary.
        try:
            parsed_sort = None
            # Query parsing needs the library root, but keeping it scoped here
            # avoids leaking one Library's directory into another's work.
            with context.music_dir(self.directory):
                if isinstance(query, str):
                    query, parsed_sort = parse_query_string(query, model_cls)
                elif isinstance(query, (list, tuple)):
                    query, parsed_sort = parse_query_parts(query, model_cls)
        except dbcore.query.InvalidQueryArgumentValueError as exc:
            raise dbcore.InvalidQueryError(query, exc)

        parsed_sort = parsed_sort or sort
        return self.get_results(
            model_cls,
            query,
            # Any non-null sort specified by the parsed query overrides the
            # provided sort.
            model_cls.default_sort if parsed_sort is None else parsed_sort,
        )

    def albums(self, *args, **kwargs) -> Results[Album]:
        """Get :class:`Album` objects matching the query."""
        return self._fetch(Album, *args, **kwargs)

    def items(self, *args, **kwargs) -> Results[Item]:
        """Get :class:`Item` objects matching the query."""
        return self._fetch(Item, *args, **kwargs)

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
