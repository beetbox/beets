from __future__ import annotations

from typing import TYPE_CHECKING

import platformdirs

import beets
from beets import dbcore, logging, ui
from beets.autotag import correct_list_fields
from beets.util import normpath

from .models import Album, Item
from .queries import PF_KEY_DEFAULT, parse_query_parts, parse_query_string

if TYPE_CHECKING:
    from collections.abc import Mapping

    from beets.dbcore import Results, types

log = logging.getLogger("beets")


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

    # Database schema migration.

    def _make_table(self, table: str, fields: Mapping[str, types.Type]):
        """Set up the schema of the database, and migrate genres if needed."""
        with self.transaction() as tx:
            rows = tx.query(f"PRAGMA table_info({table})")
        current_fields = {row[1] for row in rows}
        field_names = set(fields.keys())

        # Check if genres column is being added to items table
        genres_being_added = (
            table == "items"
            and "genres" in field_names
            and "genres" not in current_fields
            and "genre" in current_fields
        )

        # Call parent to create/update table
        super()._make_table(table, fields)

        # Migrate genre to genres if genres column was just added
        if genres_being_added:
            self._migrate_genre_to_genres()

    def _migrate_genre_to_genres(self):
        """Migrate comma-separated genre strings to genres list.

        This migration runs automatically when the genres column is first
        created in the database. It splits comma-separated genre values
        and writes the changes to both the database and media files.
        """
        items = list(self.items())
        migrated_count = 0
        total_items = len(items)

        if total_items == 0:
            return

        ui.print_(f"Migrating genres for {total_items} items...")

        for index, item in enumerate(items, 1):
            genre_val = item.genre or ""
            genres_val = item.genres or []

            # Check if migration is needed
            needs_migration = False
            split_genres = []
            if not genres_val and genre_val:
                separators = []
                if (
                    "lastgenre" in beets.config
                    and "separator" in beets.config["lastgenre"]
                ):
                    try:
                        user_sep = beets.config["lastgenre"][
                            "separator"
                        ].as_str()
                        if user_sep:
                            separators.append(user_sep)
                    except (
                        beets.config.ConfigNotFoundError,
                        beets.config.ConfigTypeError,
                    ):
                        pass

                separators.extend([", ", "; ", " / "])

                for separator in separators:
                    if separator in genre_val:
                        split_genres = [
                            g.strip()
                            for g in genre_val.split(separator)
                            if g.strip()
                        ]
                        if len(split_genres) > 1:
                            needs_migration = True
                            break

            if needs_migration:
                migrated_count += 1
                # Show progress every 100 items
                if migrated_count % 100 == 0:
                    ui.print_(
                        f"  Migrated {migrated_count} items "
                        f"({index}/{total_items} processed)..."
                    )
                # Migrate using the same logic as correct_list_fields
                correct_list_fields(item)
                item.store()
                # Write to media file
                try:
                    item.try_write()
                except Exception as e:
                    log.warning(
                        "Could not write genres to {}: {}",
                        item.path,
                        e,
                    )

        ui.print_(
            f"Migration complete: {migrated_count} of {total_items} items "
            f"updated with comma-separated genres"
        )
