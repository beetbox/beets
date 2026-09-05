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


class TestGetTrack:
    def track_data(self, **fields):
        return {
            "id": 1,
            "title": "Title",
            "duration": 100,
            "link": "https://www.deezer.com/track/1",
            **fields,
        }

    def test_uses_contributors_when_artist_is_missing(self, plugin):
        track = plugin._get_track(
            self.track_data(contributors=[{"id": 2, "name": "Artist"}])
        )

        assert track.artist == "Artist"
        assert track.artist_id == "2"

    def test_falls_back_to_artist_without_contributors(self, plugin):
        track = plugin._get_track(
            self.track_data(artist={"id": 2, "name": "Artist"})
        )

        assert track.artist == "Artist"
        assert track.artist_id == "2"

    def test_tolerates_missing_artist_and_contributors(self, plugin):
        track = plugin._get_track(self.track_data())

        assert track.artist is None
        assert track.artist_id is None
