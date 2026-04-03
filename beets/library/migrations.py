from __future__ import annotations

import os
from contextlib import suppress
from functools import cached_property
from typing import TYPE_CHECKING, NamedTuple, TypeVar

from confuse.exceptions import ConfigError

import beets
from beets import ui
from beets.dbcore.db import Migration
from beets.dbcore.pathutils import normalize_path_for_db
from beets.dbcore.types import MULTI_VALUE_DELIMITER
from beets.util import unique_list
from beets.util.lyrics import Lyrics

if TYPE_CHECKING:
    from collections.abc import Iterator

    from beets.dbcore.db import Model
    from beets.library import Library

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
    """Backfill multi-value genres from legacy single-string genre data."""

    @cached_property
    def separators(self) -> list[str]:
        """Return known separators that indicate multiple legacy genres."""
        separators = []
        with suppress(ConfigError):
            separators.append(beets.config["lastgenre"]["separator"].as_str())

        separators.extend(["; ", ", ", " / "])
        return unique_list(filter(None, separators))

    def get_genres(self, genre: str) -> str:
        """Normalize legacy genre separators to the canonical delimiter."""
        for separator in self.separators:
            if separator in genre:
                return genre.replace(separator, MULTI_VALUE_DELIMITER)

        return genre

    def _migrate_data(
        self, model_cls: type[Model], current_fields: set[str]
    ) -> None:
        """Migrate legacy genre values to the multi-value genres field."""
        if "genre" not in current_fields:
            # No legacy genre field, so nothing to migrate.
            return

        table = model_cls._table

        with self.db.transaction() as tx, self.with_row_factory(GenreRow):
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
        for batch in chunks(to_migrate, self.CHUNK_SIZE):
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


class LyricsRow(NamedTuple):
    id: int
    lyrics: str


class LyricsMetadataInFlexFieldsMigration(Migration):
    """Move legacy inline lyrics metadata into dedicated flexible fields."""

    CHUNK_SIZE = 100

    def _migrate_data(self, model_cls: type[Model], _: set[str]) -> None:
        """Migrate legacy lyrics to move metadata to flex attributes."""
        table = model_cls._table
        flex_table = model_cls._flex_table

        with self.db.transaction() as tx:
            migrated_ids = {
                r[0]
                for r in tx.query(
                    f"""
                    SELECT entity_id
                    FROM {flex_table}
                    WHERE key == 'lyrics_backend'
                    """
                )
            }
        with self.db.transaction() as tx, self.with_row_factory(LyricsRow):
            rows: list[LyricsRow] = tx.query(  # type: ignore[assignment]
                f"""
                SELECT id, lyrics
                FROM {table}
                WHERE lyrics IS NOT NULL AND lyrics != ''
                """
            )

        total = len(rows)
        to_migrate = [r for r in rows if r.id not in migrated_ids]
        if not to_migrate:
            return

        migrated = total - len(to_migrate)

        ui.print_(f"Migrating lyrics for {total} {table}...")
        lyr_fields = ["backend", "url", "language", "translation_language"]
        for batch in chunks(to_migrate, self.CHUNK_SIZE):
            lyrics_batch = [Lyrics.from_legacy_text(r.lyrics) for r in batch]
            ids_with_lyrics = [
                (lyr, r.id) for lyr, r in zip(lyrics_batch, batch)
            ]
            with self.db.transaction() as tx:
                update_rows = [
                    (lyr.full_text, r.id)
                    for lyr, r in zip(lyrics_batch, batch)
                    if lyr.full_text != r.lyrics
                ]
                if update_rows:
                    tx.mutate_many(
                        f"UPDATE {table} SET lyrics = ? WHERE id = ?",
                        update_rows,
                    )

                # Only insert flex rows for non-null metadata values
                flex_rows = [
                    (_id, f"lyrics_{field}", val)
                    for lyr, _id in ids_with_lyrics
                    for field in lyr_fields
                    if (val := getattr(lyr, field)) is not None
                ]
                if flex_rows:
                    tx.mutate_many(
                        f"""
                        INSERT INTO {flex_table} (entity_id, key, value)
                        VALUES (?, ?, ?)
                        """,
                        flex_rows,
                    )

            migrated += len(batch)

            ui.print_(
                f"  Migrated {migrated} {table} "
                f"({migrated}/{total} processed)..."
            )

        ui.print_(f"Migration complete: {migrated} of {total} {table} updated")


class RelativePathMigration(Migration):
    """Migrate path field to contain value relative to the music directory."""

    db: Library

    def _migrate_field(self, model_cls: type[Model], field: str) -> None:
        table = model_cls._table

        with self.db.transaction() as tx:
            rows = tx.query(f"SELECT id, {field} FROM {table}")  # type: ignore[assignment]

        total = len(rows)
        to_migrate = [r for r in rows if r[field] and os.path.isabs(r[field])]
        if not to_migrate:
            return

        migrated = total - len(to_migrate)
        ui.print_(f"Migrating {field} for {total} {table}...")
        for batch in chunks(to_migrate, self.CHUNK_SIZE):
            with self.db.transaction() as tx:
                tx.mutate_many(
                    f"UPDATE {table} SET {field} = ? WHERE id = ?",
                    [(normalize_path_for_db(r[field]), r["id"]) for r in batch],
                )

            migrated += len(batch)

            ui.print_(
                f"  Migrated {migrated} {table} "
                f"({migrated}/{total} processed)..."
            )

        ui.print_(f"Migration complete: {migrated} of {total} {table} updated")

    def _migrate_data(
        self, model_cls: type[Model], current_fields: set[str]
    ) -> None:
        for field in {"path", "artpath"} & current_fields:
            self._migrate_field(model_cls, field)
