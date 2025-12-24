import re
import uuid
from contextlib import nullcontext as does_not_raise

import pytest

from beets.library import Album
from beets.test.helper import ConfigMixin
from beets.ui import UserError
from beetsplug import mbcollection


@pytest.fixture
def collection():
    return mbcollection.MBCollection(
        {"id": str(uuid.uuid4()), "release-count": 150}
    )


class TestMbCollectionAPI:
    """Tests for the low-level MusicBrainz API wrapper functions."""

    def test_submit_albums_batches(self, collection, requests_mock):
        # Chunk size is 200. Create 250 IDs.
        ids = [f"id{i}" for i in range(250)]
        requests_mock.put(
            f"/ws/2/collection/{collection.id}/releases/{';'.join(ids[:200])}"
        )
        requests_mock.put(
            f"/ws/2/collection/{collection.id}/releases/{';'.join(ids[200:])}"
        )

        mbcollection.submit_albums(collection, ids)


class TestMbCollectionPlugin(ConfigMixin):
    """Tests for the MusicBrainzCollectionPlugin class methods."""

    COLLECTION_ID = str(uuid.uuid4())

    @pytest.fixture
    def plugin(self):
        self.config["musicbrainz"]["user"] = "testuser"
        self.config["musicbrainz"]["pass"] = "testpass"

        plugin = mbcollection.MusicBrainzCollectionPlugin()
        plugin.config["collection"] = self.COLLECTION_ID
        return plugin

    @pytest.mark.parametrize(
        "user_collections,expectation",
        [
            (
                [],
                pytest.raises(
                    UserError, match=r"no collections exist for user"
                ),
            ),
            (
                [{"id": "c1", "entity-type": "event"}],
                pytest.raises(UserError, match=r"No release collection found."),
            ),
            (
                [{"id": "c1", "entity-type": "release"}],
                pytest.raises(UserError, match=r"invalid collection ID"),
            ),
            (
                [{"id": COLLECTION_ID, "entity-type": "release"}],
                does_not_raise(),
            ),
        ],
    )
    def test_get_collection_validation(
        self, plugin, requests_mock, user_collections, expectation
    ):
        requests_mock.get(
            "/ws/2/collection", json={"collections": user_collections}
        )

        with expectation:
            plugin._get_collection()

    def test_get_albums_in_collection_pagination(
        self, plugin, requests_mock, collection
    ):
        releases = [{"id": str(i)} for i in range(collection.release_count)]
        requests_mock.get(
            re.compile(
                rf".*/ws/2/collection/{collection.id}/releases\b.*&offset=0.*"
            ),
            json={"releases": releases[:100]},
        )
        requests_mock.get(
            re.compile(
                rf".*/ws/2/collection/{collection.id}/releases\b.*&offset=100.*"
            ),
            json={"releases": releases[100:]},
        )

        plugin._get_albums_in_collection(collection)

    def test_update_album_list_filtering(self, plugin, collection, monkeypatch):
        ids_submitted = []

        def mock_submit(_, album_ids):
            ids_submitted.extend(album_ids)

        monkeypatch.setattr("beetsplug.mbcollection.submit_albums", mock_submit)
        monkeypatch.setattr(plugin, "_get_collection", lambda: collection)

        albums = [
            Album(mb_albumid="invalid-id"),
            Album(mb_albumid="00000000-0000-0000-0000-000000000001"),
        ]

        plugin.update_album_list(None, albums)
        # Behavior: only valid UUID was submitted
        assert ids_submitted == ["00000000-0000-0000-0000-000000000001"]

    def test_remove_missing(
        self, plugin, monkeypatch, requests_mock, collection
    ):
        removed_ids = []

        def mock_remove(_, chunk):
            removed_ids.extend(chunk)

        requests_mock.delete(
            re.compile(rf".*/ws/2/collection/{collection.id}/releases/r3")
        )
        monkeypatch.setattr(
            plugin, "_get_albums_in_collection", lambda _: {"r1", "r2", "r3"}
        )

        lib_albums = [Album(mb_albumid="r1"), Album(mb_albumid="r2")]

        plugin.remove_missing(collection, lib_albums)
