import re
import uuid
from contextlib import nullcontext as does_not_raise

import pytest
import requests

from beets.library import Album
from beets.test.helper import PluginMixin, TestHelper
from beets.ui import UserError
from beetsplug import mbcollection


class TestMbCollectionPlugin(PluginMixin, TestHelper):
    """Tests for the MusicBrainzCollectionPlugin class methods."""

    plugin = "mbcollection"

    COLLECTION_ID = str(uuid.uuid4())

    @pytest.fixture(autouse=True)
    def setup_config(self):
        self.config["musicbrainz"]["user"] = "testuser"
        self.config["musicbrainz"]["pass"] = "testpass"
        self.config["mbcollection"]["collection"] = self.COLLECTION_ID

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
                [{"id": "c1", "entity_type": "event"}],
                pytest.raises(UserError, match=r"No release collection found."),
            ),
            (
                [{"id": "c1", "entity_type": "release"}],
                pytest.raises(UserError, match=r"invalid collection ID"),
            ),
            (
                [{"id": COLLECTION_ID, "entity_type": "release"}],
                does_not_raise(),
            ),
        ],
        ids=["no collections", "no release collections", "invalid ID", "valid"],
    )
    def test_get_collection_validation(
        self, requests_mock, user_collections, expectation
    ):
        requests_mock.get(
            "/ws/2/collection", json={"collections": user_collections}
        )

        with expectation:
            mbcollection.MusicBrainzCollectionPlugin().collection

    def test_mbupdate(self, requests_mock, monkeypatch):
        """Verify mbupdate sync of a MusicBrainz collection with the library.

        This test ensures that the command:
        - fetches collection releases using paginated requests,
        - submits releases that exist locally but are missing from the remote
          collection
        - and removes releases from the remote collection that are not in the
          local library. Small chunk sizes are forced to exercise pagination and
          batching logic.
        """
        for mb_albumid in [
            # already present in remote collection
            "in_collection1",
            "in_collection2",
            # two new albums not in remote collection
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        ]:
            self.lib.add(Album(mb_albumid=mb_albumid))

        # The relevant collection
        requests_mock.get(
            "/ws/2/collection",
            json={
                "collections": [
                    {
                        "id": self.COLLECTION_ID,
                        "entity_type": "release",
                        "release_count": 3,
                    }
                ]
            },
        )

        collection_releases = f"/ws/2/collection/{self.COLLECTION_ID}/releases"
        # Force small fetch chunk to require multiple paged requests.
        monkeypatch.setattr(
            "beetsplug.mbcollection.MBCollection.FETCH_CHUNK_SIZE", 2
        )
        # 3 releases are fetched in two pages.
        requests_mock.get(
            re.compile(rf".*{collection_releases}\b.*&offset=0.*"),
            json={
                "releases": [{"id": "in_collection1"}, {"id": "not_in_library"}]
            },
        )
        requests_mock.get(
            re.compile(rf".*{collection_releases}\b.*&offset=2.*"),
            json={"releases": [{"id": "in_collection2"}]},
        )

        # Force small submission chunk
        monkeypatch.setattr(
            "beetsplug.mbcollection.MBCollection.SUBMISSION_CHUNK_SIZE", 1
        )
        # so that releases are added using two requests
        requests_mock.put(
            re.compile(
                rf".*{collection_releases}/00000000-0000-0000-0000-000000000001"
            )
        )
        requests_mock.put(
            re.compile(
                rf".*{collection_releases}/00000000-0000-0000-0000-000000000002"
            )
        )
        # and finally, one release is removed
        requests_mock.delete(
            re.compile(rf".*{collection_releases}/not_in_library")
        )

        self.run_command("mbupdate", "--remove")

        assert requests_mock.call_count == 6

    def test_mbupdate_logs_unauthorized_errors(self, requests_mock, caplog):
        response = requests.Response()
        response.status_code = 401
        requests_mock.get(
            "/ws/2/collection",
            exc=requests.exceptions.HTTPError(response=response),
        )

        with caplog.at_level("ERROR", logger="beets.mbcollection"):
            self.run_command("mbupdate")

        expected_message = (
            "Failed to update MusicBrainz collection: HTTP Error: 401"
            " Unauthorized. Check your musicbrainz.user and musicbrainz.pass"
            " configuration"
        )
        assert expected_message in caplog.text
