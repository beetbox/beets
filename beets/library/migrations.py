from __future__ import annotations

from contextlib import contextmanager, suppress
from functools import cached_property
from typing import TYPE_CHECKING, NamedTuple, TypeVar

from confuse.exceptions import ConfigError

import beets
from beets import ui
from beets.dbcore.db import Migration
from beets.dbcore.types import MULTI_VALUE_DELIMITER
from beets.util import unique_list

if TYPE_CHECKING:
    from collections.abc import Iterator

T = TypeVar("T")


class GenreRow(NamedTuple):
    id: int
    genre: str
    genres: str | None


def chunks(lst: list[T], n: int) -> Iterator[list[T]]:
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


class MultiGenreFieldMigration(Migration):
    @cached_property
    def separators(self) -> list[str]:
        separators = []
        with suppress(ConfigError):
            separators.append(beets.config["lastgenre"]["separator"].as_str())

        separators.extend(["; ", ", ", " / "])
        return unique_list(filter(None, separators))

    @contextmanager
    def with_factory(self, factory: type[NamedTuple]) -> Iterator[None]:
        """Temporarily set the row factory to a specific type."""
        original_factory = self.db._connection().row_factory
        self.db._connection().row_factory = lambda _, row: factory(*row)
        try:
            yield
        finally:
            self.db._connection().row_factory = original_factory

    def get_genres(self, genre: str) -> str:
        for separator in self.separators:
            if separator in genre:
                return genre.replace(separator, MULTI_VALUE_DELIMITER)

        return genre

    def _migrate_data(self, table: str, current_fields: set[str]) -> None:
        """Migrate legacy genre values to the multi-value genres field."""
        if "genre" not in current_fields:
            # No legacy genre field, so nothing to migrate.
            return

        with self.db.transaction() as tx, self.with_factory(GenreRow):
            rows: list[GenreRow] = tx.query(  # type: ignore[assignment]
                f"""
                SELECT id, genre, genres
                FROM {table}
                WHERE genre IS NOT NULL AND genre != ''
                """
            )

        total = len(rows)
        to_migrate = [e for e in rows if not e.genres]
        if not to_migrate:
            return

        migrated = total - len(to_migrate)

        ui.print_(f"Migrating genres for {total} {table}...")
        for batch in chunks(to_migrate, 1000):
            with self.db.transaction() as tx:
                tx.mutate_many(
                    f"UPDATE {table} SET genres = ? WHERE id = ?",
                    [(self.get_genres(e.genre), e.id) for e in batch],
                )

            migrated += len(batch)

            ui.print_(
                f"  Migrated {migrated} {table} "
                f"({migrated}/{total} processed)..."
            )

        ui.print_(f"Migration complete: {migrated} of {total} {table} updated")
