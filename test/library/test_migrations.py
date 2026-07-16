import os
import textwrap
from pathlib import Path
from typing import ClassVar

import pytest

from beets.dbcore import types
from beets.library import migrations
from beets.library.models import Album, Item
from beets.test.helper import TestHelper
from beets.util import cached_classproperty, path_as_posix

Migration = tuple[
    type[migrations.Migration], tuple[type[Item] | type[Album], ...]
]


class MigrationTestHelper(TestHelper):
    """Provide a shared harness for exercising one library migration at a time.

    The helper builds a library that starts in a pre-migration state, then
    re-enables the migration under test so each subclass can verify the data
    transformation in isolation.
    """

    migration: ClassVar[Migration]

    @classmethod
    def setup_previous_state(cls, monkeypatch: pytest.MonkeyPatch) -> None:
        """Shape the library into the legacy state expected by the migration.

        Subclasses override this hook to create older schema or metadata
        layouts before the test library is initialized.
        """

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        """Initialize the test library around the migration under test.

        The fixture first prevents automatic migrations so legacy test data can
        be created safely, then restores the target migration and tears down the
        temporary library after each test.
        """
        # do not apply migrations upon library initialization
        monkeypatch.setattr("beets.library.library.Library._migrations", ())
        self.setup_previous_state(monkeypatch)

        self.setup_beets()

        # and now configure the migrations to be tested
        monkeypatch.setattr(
            "beets.library.library.Library._migrations", (self.migration,)
        )
        try:
            yield
        finally:
            self.teardown_beets()


class TestMultiGenreFieldMigration(MigrationTestHelper):
    """Verify legacy single-value genres are promoted to multi-value fields."""

    migration = (migrations.MultiGenreFieldMigration, (Item, Album))

    @classmethod
    def setup_previous_state(cls, monkeypatch: pytest.MonkeyPatch) -> None:
        """Expose the legacy genre columns required to exercise the migration."""
        # add genre field to both models to make sure this column is created
        monkeypatch.setattr(
            "beets.library.models.Item._fields",
            {**Item._fields, "genre": types.STRING},
        )
        monkeypatch.setattr(
            "beets.library.models.Album._fields",
            {**Album._fields, "genre": types.STRING},
        )
        monkeypatch.setattr(
            "beets.library.models.Album.item_keys", {*Album.item_keys, "genre"}
        )

    def test_migrate(self):
        """Ensure genre data is split once and preserved when already populated."""
        self.config["lastgenre"]["separator"] = " - "

        expected_item_genres = []
        for genre, initial_genres, expected_genres in [
            # already existing value is not overwritten
            ("Item Rock", ("Ignored",), ("Ignored",)),
            ("", (), ()),
            ("Rock", (), ("Rock",)),
            # multiple genres are split on one of default separators
            ("Item Rock; Alternative", (), ("Item Rock", "Alternative")),
            # multiple genres are split the first (lastgenre) separator ONLY
            ("Item - Rock, Alternative", (), ("Item", "Rock, Alternative")),
        ]:
            self.add_item(genre=genre, genres=initial_genres)
            expected_item_genres.append(expected_genres)

        unmigrated_album = self.add_album(
            genre="Album Rock / Alternative", genres=[]
        )
        expected_item_genres.append(("Album Rock", "Alternative"))

        self.lib._migrate()

        actual_item_genres = [tuple(i.genres) for i in self.lib.items()]
        assert actual_item_genres == expected_item_genres

        unmigrated_album.load()
        assert unmigrated_album.genres == ["Album Rock", "Alternative"]

        # remove cached initial db tables data
        del self.lib.db_tables
        assert self.lib.migration_exists("multi_genre_field", "items")
        assert self.lib.migration_exists("multi_genre_field", "albums")


class MultiArtistFieldMigrationTestMixin(MigrationTestHelper):
    """Share coverage for migrations that split artist-like text into lists."""

    str_field: ClassVar[str]
    list_field: ClassVar[str]
    migration_cls: ClassVar[type[migrations.MultiValueFieldMigration]]

    @cached_classproperty
    def migration(cls) -> Migration:
        """Bind each concrete test class to its corresponding migration."""
        return (cls.migration_cls, (Item,))

    @classmethod
    def setup_previous_state(cls, monkeypatch: pytest.MonkeyPatch) -> None:
        """Expose the legacy scalar field expected by the migration."""
        # add legacy str field to make sure this column is created
        monkeypatch.setattr(
            "beets.library.models.Item._fields",
            {**Item._fields, cls.str_field: types.STRING},
        )

    def test_migrate(self):
        """Ensure existing list values win and legacy text splits consistently."""
        expected_list_values = []
        for str_value, initial_list_value, expected_list_value in [
            # already existing value is not overwritten
            ("Artist", ("Ignored",), ("Ignored",)),
            ("", (), ()),
            ("Artist", (), ("Artist",)),
            # multiple values are split on one of separators
            ("Artist; Another Artist", (), ("Artist", "Another Artist")),
            # multiple values are split by the existing separator ONLY
            ("Artist, Another; Artist", (), ("Artist, Another", "Artist")),
        ]:
            data = {
                self.str_field: str_value,
                self.list_field: initial_list_value,
            }
            self.add_item(**data)
            expected_list_values.append(expected_list_value)

        self.lib._migrate()

        actual_list_values = [
            tuple(i[self.list_field]) for i in self.lib.items()
        ]
        assert actual_list_values == expected_list_values

        # remove cached initial db tables data
        del self.lib.db_tables
        assert self.lib.migration_exists(
            f"multi_{self.str_field}_field", "items"
        )


class TestMultiRemixerFieldMigration(MultiArtistFieldMigrationTestMixin):
    str_field = "remixer"
    list_field = "remixers"
    migration_cls = migrations.MultiRemixerFieldMigration


class TestMultiLyricistFieldMigration(MultiArtistFieldMigrationTestMixin):
    str_field = "lyricist"
    list_field = "lyricists"
    migration_cls = migrations.MultiLyricistFieldMigration


class TestMultiComposerFieldMigration(MultiArtistFieldMigrationTestMixin):
    str_field = "composer"
    list_field = "composers"
    migration_cls = migrations.MultiComposerFieldMigration


class TestMultiArrangerFieldMigration(MultiArtistFieldMigrationTestMixin):
    str_field = "arranger"
    list_field = "arrangers"
    migration_cls = migrations.MultiArrangerFieldMigration


class TestLyricsMetadataInFlexFieldsMigration(MigrationTestHelper):
    """Verify embedded lyrics metadata moves into dedicated flexible fields."""

    migration = (migrations.LyricsMetadataInFlexFieldsMigration, (Item,))

    def test_migrate(self, is_importable):
        """Ensure extracted metadata is preserved without mutating plain lyrics."""
        lyrics_item = self.add_item(
            lyrics=textwrap.dedent("""
            [00:00.00] Some synced lyrics / Quelques paroles synchronisées
            [00:00.50]
            [00:01.00] Some more synced lyrics / Quelques paroles plus synchronisées

            Source: https://lrclib.net/api/1/""")
        )
        instrumental_lyrics_item = self.add_item(lyrics="[Instrumental]")

        self.lib._migrate()

        lyrics_item.load()

        assert lyrics_item.lyrics == textwrap.dedent(
            """
            [00:00.00] Some synced lyrics / Quelques paroles synchronisées
            [00:00.50]
            [00:01.00] Some more synced lyrics / Quelques paroles plus synchronisées"""
        )
        assert lyrics_item.lyrics_backend == "lrclib"
        assert lyrics_item.lyrics_url == "https://lrclib.net/api/1/"

        if is_importable("langdetect"):
            assert lyrics_item.lyrics_language == "EN"
            assert lyrics_item.lyrics_translation_language == "FR"
        else:
            with pytest.raises(AttributeError):
                instrumental_lyrics_item.lyrics_language
            with pytest.raises(AttributeError):
                instrumental_lyrics_item.lyrics_translation_language

        with pytest.raises(AttributeError):
            instrumental_lyrics_item.lyrics_backend
        with pytest.raises(AttributeError):
            instrumental_lyrics_item.lyrics_url
        with pytest.raises(AttributeError):
            instrumental_lyrics_item.lyrics_language
        with pytest.raises(AttributeError):
            instrumental_lyrics_item.lyrics_translation_language

        # remove cached initial db tables data
        del self.lib.db_tables
        assert self.lib.migration_exists(
            "lyrics_metadata_in_flex_fields", "items"
        )


class TestRemoveInheritedArtpathMigration(MigrationTestHelper):
    """Verify inherited artpath flex attributes are removed from items."""

    migration = (migrations.RemoveInheritedArtpathMigration, (Item,))

    def test_migrate(self):
        """Ensure the inherited artpath flex attribute is removed from items."""
        item = self.add_item(artpath="/abs/path/to/cover.jpg")

        self.lib._migrate()

        item.load()
        with pytest.raises(AttributeError):
            item.artpath

        # remove cached initial db tables data
        del self.lib.db_tables
        assert self.lib.migration_exists("remove_inherited_artpath", "items")


class TestRelativePathMigration(MigrationTestHelper):
    """Verify stored item paths are rewritten to library-relative values."""

    migration = (migrations.RelativePathMigration, (Item,))

    def test_migrate(self):
        """Ensure stored paths become relative while the public API stays stable."""
        relative_path = str(Path("foo") / "bar" / "baz.mp3")
        abs_string_path = str(self.lib_path / relative_path)
        abs_bytes_path = os.fsencode(abs_string_path)

        # need to insert the path directly into the database to bypass the path setter
        self.lib._connection().executemany(
            "INSERT INTO items (id, path) VALUES (?, ?)",
            (
                (1, abs_bytes_path),
                # add a string path to ensure the migration handles it
                (2, abs_string_path),
            ),
        )
        old_stored_path = (
            self.lib._connection()
            .execute("select path from items where id=?", (1,))
            .fetchone()[0]
        )
        assert old_stored_path == abs_bytes_path

        self.lib._migrate()

        item = self.lib.get_item(1)
        assert item

        # and now we have a relative path
        stored_path = (
            self.lib._connection()
            .execute("select path from items where id=?", (item.id,))
            .fetchone()[0]
        )
        assert stored_path == path_as_posix(os.fsencode(relative_path))
        # and the item.path property still returns an absolute path
        assert item.path == abs_bytes_path

        # also check the string path was migrated correctly
        str_item = self.lib.get_item(2)
        assert str_item
        assert str_item.path == abs_bytes_path


class TestMigrationBackup(MigrationTestHelper):
    """Tests for the backup-before-migration feature."""

    migration = (migrations.LyricsMetadataInFlexFieldsMigration, (Item,))
    db_on_disk = True

    @classmethod
    def setup_previous_state(cls, monkeypatch):
        monkeypatch.setattr(
            "beets.library.models.Item._fields",
            {**Item._fields, "lyrics": types.STRING},
        )

    @pytest.mark.parametrize(
        "config_value, expected_count", [(True, 1), (False, 0)]
    )
    def test_backup_config(self, config_value, expected_count):
        self.config["create_backup_before_migrations"] = config_value
        self.add_item(lyrics="some lyrics")
        db_path = self.lib_path

        self.lib._migrate()

        backups = [
            f
            for f in db_path.parent.iterdir()
            if os.fsdecode(f).endswith(".bak")
        ]
        assert len(backups) == expected_count


class TestInstrumentalLyricsInFlexFieldMigration(MigrationTestHelper):
    """Verify legacy instrumental markers move out of canonical lyrics."""

    migration = (migrations.InstrumentalLyricsInFlexFieldMigration, (Item,))

    def test_migrate(self):
        """Ensure exact instrumental markers become metadata, not lyric text."""
        instrumental_item = self.add_item(lyrics="[Instrumental]")
        regular_item = self.add_item(lyrics="Regular lyrics")

        self.lib._migrate()

        instrumental_item.load()
        regular_item.load()

        assert instrumental_item.lyrics == ""
        assert instrumental_item.lyrics_instrumental == "1"
        assert regular_item.lyrics == "Regular lyrics"

        with pytest.raises(AttributeError, match="lyrics_instrumental"):
            regular_item.lyrics_instrumental

        # remove cached initial db tables data
        del self.lib.db_tables
        assert self.lib.migration_exists(
            "instrumental_lyrics_in_flex_field", "items"
        )
