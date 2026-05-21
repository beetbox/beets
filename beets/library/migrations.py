from __future__ import annotations

import os
from contextlib import suppress
from functools import cached_property
from typing import TYPE_CHECKING, ClassVar, NamedTuple

from confuse.exceptions import ConfigError

import beets
from beets import ui
from beets.dbcore.db import Migration
from beets.dbcore.pathutils import normalize_path_for_db
from beets.dbcore.types import MULTI_VALUE_DELIMITER
from beets.util import chunks, unique_list
from beets.util.lyrics import Lyrics

if TYPE_CHECKING:
    from beets.dbcore.db import Model
    from beets.library import Library


class MultiValueFieldMigration(Migration):
    """Backfill multi-valued field from legacy single-string values."""

    str_field: ClassVar[str]
    list_field: ClassVar[str]

    @cached_property
    def separators(self) -> list[str]:
        return ["; ", ", ", " / "]

    def convert_to_list_value(self, str_value: str) -> str:
        """Normalize legacy str value separators to the canonical delimiter."""
        for separator in self.separators:
            if separator in str_value:
                return str_value.replace(separator, MULTI_VALUE_DELIMITER)

        return str_value

    def _migrate_data(
        self, model_cls: type[Model], current_fields: set[str]
    ) -> None:
        """Migrate legacy single-valued field to multi-valued field."""
        str_field, list_field = self.str_field, self.list_field
        if str_field not in current_fields:
            # No legacy single-value field, so nothing to migrate.
            return

        table = model_cls._table

        with self.db.transaction() as tx:
            rows = tx.query(  # type: ignore[assignment]
                f"""
                SELECT id, {str_field}, {list_field}
                FROM {table}
                WHERE {str_field} IS NOT NULL AND {str_field} != ''
                """
            )

        total = len(rows)
        to_migrate = [e for e in rows if not e[list_field]]
        if not to_migrate:
            return

        migrated = total - len(to_migrate)

        ui.print_(f"Migrating {list_field} for {total} {table}...")
        for batch in chunks(to_migrate, self.CHUNK_SIZE):
            with self.db.transaction() as tx:
                tx.mutate_many(
                    f"UPDATE {table} SET {list_field} = ? WHERE id = ?",
                    [
                        (self.convert_to_list_value(e[str_field]), e["id"])
                        for e in batch
                    ],
                )

            migrated += len(batch)

            ui.print_(
                f"  Migrated {migrated} {table} "
                f"({migrated}/{total} processed)..."
            )

        ui.print_(f"Migration complete: {migrated} of {total} {table} updated")


class MultiGenreFieldMigration(MultiValueFieldMigration):
    """Backfill multi-valued genres from legacy single-string genre data."""

    str_field = "genre"
    list_field = "genres"

    @cached_property
    def separators(self) -> list[str]:
        """Return known separators that indicate multiple legacy genres."""
        separators = []
        with suppress(ConfigError):
            separators.append(beets.config["lastgenre"]["separator"].as_str())

        separators.extend(super().separators)
        return unique_list(filter(None, separators))


class MultiRemixerFieldMigration(MultiValueFieldMigration):
    """Backfill multi-valued remixers from legacy single-string remixer data."""

    str_field = "remixer"
    list_field = "remixers"


class MultiLyricistFieldMigration(MultiValueFieldMigration):
    """Backfill multi-valued lyricists from legacy single-string lyricist data."""

    str_field = "lyricist"
    list_field = "lyricists"


class MultiComposerFieldMigration(MultiValueFieldMigration):
    """Backfill multi-valued composers from legacy single-string composer data."""

    str_field = "composer"
    list_field = "composers"


class MultiArrangerFieldMigration(MultiValueFieldMigration):
    """Backfill multi-valued arrangers from legacy single-string arranger data."""

    str_field = "arranger"
    list_field = "arrangers"


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
            rows = tx.query(
                f"""
                SELECT id, {field}
                FROM {table}
                WHERE {field} IS NOT NULL
                """
            )

        total = len(rows)
        to_migrate = [r for r in rows if r[field] and os.path.isabs(r[field])]
        if not to_migrate:
            return

        ui.print_(f"Migrating {field} for {total} {table}...")
        with self.db.transaction() as tx:
            tx.mutate_many(
                f"UPDATE {table} SET {field} = ? WHERE id = ?",
                [
                    # Convert to bytes in case a user has manually set paths to
                    # a TEXT value
                    (normalize_path_for_db(os.fsencode(r[field])), r["id"])
                    for r in to_migrate
                ],
            )

        ui.print_(
            f"Migration complete: {len(to_migrate)} of {total} {table} updated"
        )

    def _migrate_data(
        self, model_cls: type[Model], current_fields: set[str]
    ) -> None:
        for field in {"path", "artpath"} & current_fields:
            self._migrate_field(model_cls, field)
