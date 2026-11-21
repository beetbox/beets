from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import pytest

from beets.dbcore.types import MULTI_VALUE_DELIMITER

if TYPE_CHECKING:
    from flask.testing import Client


@pytest.fixture(scope="module")
def helper(module_helper):
    return module_helper


@pytest.fixture(scope="module")
def app(helper):
    from beetsplug.aura import create_app

    app = create_app()
    # Close the on-disk library opened by ``create_app``: we do not use it, and
    # its open file handle stops Windows removing the temp dir during teardown.
    app.config["lib"]._close()
    app.config["lib"] = helper.lib
    return app


@pytest.fixture(scope="module")
def item(helper):
    return helper.add_item_fixture(
        album="Album",
        title="Title",
        artist="Artist",
        albumartist="Album Artist",
        genres=["rock", "pop"],
        track=2,
    )


@pytest.fixture(scope="module")
def album(helper, item):
    return helper.lib.add_album([item])


@pytest.fixture(scope="module", autouse=True)
def _other_album_and_item(helper):
    """Add another item and album to prove that filtering works."""
    item = helper.add_item_fixture(
        album="Other Album",
        title="Other Title",
        artist="Other Artist",
        albumartist="Other Album Artist",
    )
    helper.lib.add_album([item])


class TestAuraResponse:
    @pytest.fixture
    def get_response_data(self, client: Client, item):
        """Return a callback accepting `endpoint` and `params` parameters."""

        def get(endpoint: str, params: dict[str, str]) -> dict[str, Any] | None:
            """Add additional `params` and GET the given endpoint.

            `include` parameter is added to every call to check that the
            functionality that fetches related entities works.

            Before returning the response data, ensure that the request is
            successful.
            """
            response = client.get(
                endpoint,
                query_string={"include": "tracks,artists,albums", **params},
            )

            assert response.status_code == HTTPStatus.OK

            return response.json

        return get

    @pytest.fixture(scope="class")
    @classmethod
    def track_document(cls, item, album):
        return {
            "type": "track",
            "id": str(item.id),
            "attributes": {
                "album": item.album,
                "albumartist": item.albumartist,
                "artist": item.artist,
                "genre": item.genres,
                "genres": item.genres,
                "size": item.filepath.stat().st_size,
                "title": item.title,
                "track": item.track,
            },
            "relationships": {
                "albums": {"data": [{"id": str(album.id), "type": "album"}]},
                "artists": {"data": [{"id": item.artist, "type": "artist"}]},
            },
        }

    @pytest.fixture(scope="class")
    @classmethod
    def artist_document(cls, item):
        return {
            "type": "artist",
            "id": item.artist,
            "attributes": {"name": item.artist},
            "relationships": {
                "tracks": {"data": [{"id": str(item.id), "type": "track"}]}
            },
        }

    @pytest.fixture(scope="class")
    @classmethod
    def album_document(cls, album):
        return {
            "type": "album",
            "id": str(album.id),
            "attributes": {
                "artist": album.albumartist,
                "title": album.album,
                "genre": album.genres,
                "genres": album.genres,
            },
            "relationships": {
                "tracks": {"data": [{"id": str(album.id), "type": "track"}]}
            },
        }

    def test_tracks(
        self,
        get_response_data,
        item,
        album_document,
        artist_document,
        track_document,
    ):
        """Test tracks response.

        1. Filter by a field which has an int type.
        2. Sort by a field that has no value: make sure the item is included in
           the response.
        """
        data = get_response_data(
            "/aura/tracks", {"filter[track]": item.track, "sort": "mb_trackid"}
        )

        assert data == {
            "data": [track_document],
            "included": [artist_document, album_document],
        }

    def test_artists(
        self, get_response_data, item, artist_document, track_document
    ):
        data = get_response_data(
            "/aura/artists", {"filter[artist]": item.artist}
        )

        assert data == {"data": [artist_document], "included": [track_document]}

    def test_albums(
        self, get_response_data, album, album_document, track_document
    ):
        """Test albums response.

        1. Filter by a field which has a list type.
        """
        data = get_response_data(
            "/aura/albums",
            {"filter[genres]": MULTI_VALUE_DELIMITER.join(album.genres)},
        )

        assert data == {"data": [album_document], "included": [track_document]}
