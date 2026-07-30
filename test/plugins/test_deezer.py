import pytest

from beets.library import Item
from beetsplug.deezer import DeezerPlugin


@pytest.fixture
def plugin():
    return DeezerPlugin()


class TestSearchQuery:
    def test_track_query_is_free_text(self, plugin):
        query, filters = plugin.get_search_query_with_filters(
            "track", [Item()], "Artist", "Title", False
        )

        assert query == "Title Artist"
        assert filters == {}

    def test_track_query_tolerates_missing_artist(self, plugin):
        query, _ = plugin.get_search_query_with_filters(
            "track", [Item()], "", "Title", False
        )

        assert query == "Title"

    def test_album_query_filters_on_album_and_artist(self, plugin):
        query, filters = plugin.get_search_query_with_filters(
            "album", [Item()], "Artist", "Album", False
        )

        assert query == 'album:"Album" artist:"Artist"'
        assert filters == {}

    def test_album_query_omits_artist_for_various_artists(self, plugin):
        query, _ = plugin.get_search_query_with_filters(
            "album", [Item()], "Various Artists", "Album", True
        )

        assert query == 'album:"Album"'
