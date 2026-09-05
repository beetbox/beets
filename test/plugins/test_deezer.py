from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from beets.library import Item
from beetsplug.deezer import DeezerPlugin

if TYPE_CHECKING:
    from requests_mock import Mocker

JSONDict = dict[str, Any]


@pytest.fixture
def plugin() -> DeezerPlugin:
    return DeezerPlugin()


class TestSearchQuery:
    def test_track_query_is_free_text(self, plugin: DeezerPlugin) -> None:
        query, filters = plugin.get_search_query_with_filters(
            "track", [Item()], "Artist", "Title", False
        )

        assert query == "Title Artist"
        assert filters == {}

    def test_track_query_tolerates_missing_artist(
        self, plugin: DeezerPlugin
    ) -> None:
        query, _ = plugin.get_search_query_with_filters(
            "track", [Item()], "", "Title", False
        )

        assert query == "Title"

    def test_album_query_filters_on_album_and_artist(
        self, plugin: DeezerPlugin
    ) -> None:
        query, filters = plugin.get_search_query_with_filters(
            "album", [Item()], "Artist", "Album", False
        )

        assert query == 'album:"Album" artist:"Artist"'
        assert filters == {}

    def test_album_query_omits_artist_for_various_artists(
        self, plugin: DeezerPlugin
    ) -> None:
        query, _ = plugin.get_search_query_with_filters(
            "album", [Item()], "Various Artists", "Album", True
        )

        assert query == 'album:"Album"'


def make_track(artist_id: int, position: int) -> JSONDict:
    """Build a minimal Deezer track payload credited to ``artist_id``."""
    return {
        "title": f"Track {position}",
        "id": 1000 + position,
        "link": f"https://www.deezer.com/track/{1000 + position}",
        "duration": 200,
        "track_position": position,
        "disk_number": 1,
        "artist": {"id": artist_id, "name": f"Artist {artist_id}"},
    }


class TestGetTrack:
    def track_data(self, **fields) -> JSONDict:
        return {
            "id": 1,
            "title": "Title",
            "duration": 100,
            "link": "https://www.deezer.com/track/1",
            **fields,
        }

    def test_uses_contributors_when_artist_is_missing(
        self, plugin: DeezerPlugin
    ) -> None:
        track = plugin._get_track(
            self.track_data(contributors=[{"id": 2, "name": "Artist"}])
        )

        assert track.artist == "Artist"
        assert track.artist_id == "2"

    def test_falls_back_to_artist_without_contributors(
        self, plugin: DeezerPlugin
    ) -> None:
        track = plugin._get_track(
            self.track_data(artist={"id": 2, "name": "Artist"})
        )

        assert track.artist == "Artist"
        assert track.artist_id == "2"

    def test_tolerates_missing_artist_and_contributors(
        self, plugin: DeezerPlugin
    ) -> None:
        track = plugin._get_track(self.track_data())

        assert track.artist is None
        assert track.artist_id is None


class TestVariousArtistsDetection:
    def make_album(
        self, album_artist_id: int, contributor_ids: list[int]
    ) -> JSONDict:
        """Build a minimal Deezer album payload."""
        return {
            "title": "Some Album",
            "link": "https://www.deezer.com/album/1",
            "record_type": "album",
            "label": "Some Label",
            "release_date": "2017-01-01",
            "artist": {
                "id": album_artist_id,
                "name": f"Artist {album_artist_id}",
            },
            "contributors": [
                {"id": aid, "name": f"Artist {aid}"} for aid in contributor_ids
            ],
            "cover_xl": None,
        }

    def mock_album(
        self,
        requests_mock: Mocker,
        album_artist_id: int,
        track_artist_ids: list[int],
        contributor_ids: list[int] | None = None,
    ) -> None:
        """Mock the album and album-tracks endpoints for album id 1.

        ``contributor_ids`` overrides the album-level contributors, which
        otherwise cover every artist involved.
        """
        if contributor_ids is None:
            contributor_ids = list(
                dict.fromkeys([album_artist_id, *track_artist_ids])
            )
        requests_mock.get(
            f"{DeezerPlugin.album_url}1",
            json=self.make_album(album_artist_id, contributor_ids),
        )
        requests_mock.get(
            f"{DeezerPlugin.album_url}1/tracks",
            json={
                "data": [
                    make_track(aid, i)
                    for i, aid in enumerate(track_artist_ids, start=1)
                ]
            },
        )

    def test_compilation_with_non_va_album_artist(
        self, plugin: DeezerPlugin, requests_mock: Mocker
    ) -> None:
        # Album credited to a single "main" artist that performs on only one
        # of many tracks: this is a compilation and should be flagged as VA.
        self.mock_album(
            requests_mock,
            album_artist_id=100,
            track_artist_ids=[100, 200, 300, 400, 500, 600],
        )

        album_info = plugin.album_for_id("1")

        assert album_info is not None
        assert album_info.va is True
        assert album_info.artist == "Various Artists"

    def test_plurality_artist_album_not_va(
        self, plugin: DeezerPlugin, requests_mock: Mocker
    ) -> None:
        # Album whose main artist performs on 2 of 5 tracks (40%) is above
        # the importer's single-artist threshold and stays single-artist.
        self.mock_album(
            requests_mock,
            album_artist_id=100,
            track_artist_ids=[100, 100, 200, 300, 400],
            contributor_ids=[100],
        )

        album_info = plugin.album_for_id("1")

        assert album_info is not None
        assert album_info.va is False
        assert album_info.artist == "Artist 100"

    def test_single_artist_album_not_va(
        self, plugin: DeezerPlugin, requests_mock: Mocker
    ) -> None:
        # Album whose main artist performs on every track is not a compilation.
        self.mock_album(
            requests_mock,
            album_artist_id=100,
            track_artist_ids=[100, 100, 100, 100],
        )

        album_info = plugin.album_for_id("1")

        assert album_info is not None
        assert album_info.va is False
        assert album_info.artist == "Artist 100"
