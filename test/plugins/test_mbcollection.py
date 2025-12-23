import uuid
from contextlib import nullcontext as does_not_raise

import pytest

from beets.library import Album
from beets.test.helper import ConfigMixin
from beets.ui import UserError
from beetsplug import mbcollection


class TestMbCollectionAPI:
    """Tests for the low-level MusicBrainz API wrapper functions."""

    def test_submit_albums_batches(self, monkeypatch):
        chunks_received = []

        def mock_add(collection_id, chunk):
            chunks_received.append(chunk)

        monkeypatch.setattr(
            "musicbrainzngs.add_releases_to_collection", mock_add
        )

        # Chunk size is 200. Create 250 IDs.
        ids = [f"id{i}" for i in range(250)]
        mbcollection.submit_albums("coll_id", ids)

        # Verify behavioral outcome: 2 batches were sent
        assert len(chunks_received) == 2
        assert len(chunks_received[0]) == 200
        assert len(chunks_received[1]) == 50


class TestMbCollectionPlugin(ConfigMixin):
    """Tests for the MusicBrainzCollectionPlugin class methods."""

    COLLECTION_ID = str(uuid.uuid4())

    @pytest.fixture
    def plugin(self, monkeypatch):
        # Prevent actual auth call during init
        monkeypatch.setattr("musicbrainzngs.auth", lambda *a, **k: None)

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
        self, plugin, monkeypatch, user_collections, expectation
    ):
        mock_resp = {"collection-list": user_collections}
        monkeypatch.setattr("musicbrainzngs.get_collections", lambda: mock_resp)

        with expectation:
            plugin._get_collection()

    def test_get_albums_in_collection_pagination(self, plugin, monkeypatch):
        fetched_offsets = []

        def mock_get_releases(collection_id, limit, offset):
            fetched_offsets.append(offset)
            count = 150
            # Return IDs based on offset to verify order/content
            start = offset
            end = min(offset + limit, count)
            return {
                "collection": {
                    "release-count": count,
                    "release-list": [
                        {"id": f"r{i}"} for i in range(start, end)
                    ],
                }
            }

        monkeypatch.setattr(
            "musicbrainzngs.get_releases_in_collection", mock_get_releases
        )

        albums = plugin._get_albums_in_collection("cid")
        assert len(albums) == 150
        assert fetched_offsets == [0, 100]
        assert albums[0] == "r0"
        assert albums[149] == "r149"

    def test_update_album_list_filtering(self, plugin, monkeypatch):
        ids_submitted = []

        def mock_submit(_, album_ids):
            ids_submitted.extend(album_ids)

        monkeypatch.setattr("beetsplug.mbcollection.submit_albums", mock_submit)
        monkeypatch.setattr(plugin, "_get_collection", lambda: "cid")

        albums = [
            Album(mb_albumid="invalid-id"),
            Album(mb_albumid="00000000-0000-0000-0000-000000000001"),
        ]

        plugin.update_album_list(None, albums)
        # Behavior: only valid UUID was submitted
        assert ids_submitted == ["00000000-0000-0000-0000-000000000001"]

    def test_remove_missing(self, plugin, monkeypatch):
        removed_ids = []

        def mock_remove(_, chunk):
            removed_ids.extend(chunk)

        monkeypatch.setattr(
            "musicbrainzngs.remove_releases_from_collection", mock_remove
        )
        monkeypatch.setattr(
            plugin,
            "_get_albums_in_collection",
            lambda _: ["r1", "r2", "r3"],
        )

        lib_albums = [Album(mb_albumid="r1"), Album(mb_albumid="r2")]

        plugin.remove_missing("cid", lib_albums)
        # Behavior: only 'r3' (missing from library) was removed from collection
        assert removed_ids == ["r3"]
