import textwrap

import pytest

from beets.dbcore import types
from beets.library import migrations
from beets.library.models import Album, Item
from beets.test.helper import TestHelper


class TestMultiGenreFieldMigration:
    @pytest.fixture
    def helper(self, monkeypatch):
        # do not apply migrations upon library initialization
        monkeypatch.setattr("beets.library.library.Library._migrations", ())
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
            "beets.library.models.Album.item_keys",
            {*Album.item_keys, "genre"},
        )
        helper = TestHelper()
        helper.setup_beets()

        # and now configure the migrations to be tested
        monkeypatch.setattr(
            "beets.library.library.Library._migrations",
            ((migrations.MultiGenreFieldMigration, (Item, Album)),),
        )
        yield helper

        helper.teardown_beets()

    def test_migrate(self, helper: TestHelper):
        helper.config["lastgenre"]["separator"] = " - "

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
            helper.add_item(genre=genre, genres=initial_genres)
            expected_item_genres.append(expected_genres)

        unmigrated_album = helper.add_album(
            genre="Album Rock / Alternative", genres=[]
        )
        expected_item_genres.append(("Album Rock", "Alternative"))

        helper.lib._migrate()

        actual_item_genres = [tuple(i.genres) for i in helper.lib.items()]
        assert actual_item_genres == expected_item_genres

        unmigrated_album.load()
        assert unmigrated_album.genres == ["Album Rock", "Alternative"]

        # remove cached initial db tables data
        del helper.lib.db_tables
        assert helper.lib.migration_exists("multi_genre_field", "items")
        assert helper.lib.migration_exists("multi_genre_field", "albums")


class TestMultiRemixerFieldMigration:
    @pytest.fixture
    def helper(self, monkeypatch):
        # do not apply migrations upon library initialization
        monkeypatch.setattr("beets.library.library.Library._migrations", ())
        # add remixer field to make sure this column is created
        monkeypatch.setattr(
            "beets.library.models.Item._fields",
            {**Item._fields, "remixer": types.STRING},
        )
        helper = TestHelper()
        helper.setup_beets()

        # and now configure the migrations to be tested
        monkeypatch.setattr(
            "beets.library.library.Library._migrations",
            ((migrations.MultiRemixerFieldMigration, (Item,)),),
        )
        yield helper

        helper.teardown_beets()

    def test_migrate(self, helper: TestHelper):
        expected_list_values = []
        for str_value, initial_list_value, expected_list_value in [
            # already existing value is not overwritten
            ("Artist", ("Ignored",), ("Ignored",)),
            ("", (), ()),
            ("Artist", (), ("Artist",)),
            # multiple values are split on one of default separators
            ("Artist; Another Artist", (), ("Artist", "Another Artist")),
            # multiple values are split by the existing separator ONLY
            ("Artist, Another; Artist", (), ("Artist, Another", "Artist")),
        ]:
            helper.add_item(remixer=str_value, remixers=initial_list_value)
            expected_list_values.append(expected_list_value)

        helper.lib._migrate()

        actual_list_values = [tuple(i.remixers) for i in helper.lib.items()]
        assert actual_list_values == expected_list_values

        # remove cached initial db tables data
        del helper.lib.db_tables
        assert helper.lib.migration_exists("multi_remixer_field", "items")


class TestLyricsMetadataInFlexFieldsMigration:
    @pytest.fixture
    def helper(self, monkeypatch):
        # do not apply migrations upon library initialization
        monkeypatch.setattr("beets.library.library.Library._migrations", ())

        helper = TestHelper()
        helper.setup_beets()

        # and now configure the migrations to be tested
        monkeypatch.setattr(
            "beets.library.library.Library._migrations",
            ((migrations.LyricsMetadataInFlexFieldsMigration, (Item,)),),
        )
        yield helper

        helper.teardown_beets()

    def test_migrate(self, helper: TestHelper, is_importable):
        lyrics_item = helper.add_item(
            lyrics=textwrap.dedent("""
            [00:00.00] Some synced lyrics / Quelques paroles synchronisées
            [00:00.50]
            [00:01.00] Some more synced lyrics / Quelques paroles plus synchronisées

            Source: https://lrclib.net/api/1/""")
        )
        instrumental_lyrics_item = helper.add_item(lyrics="[Instrumental]")

        helper.lib._migrate()

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
        del helper.lib.db_tables
        assert helper.lib.migration_exists(
            "lyrics_metadata_in_flex_fields", "items"
        )
