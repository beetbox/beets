import pytest

from beets.test.helper import ConfigMixin
from beetsplug.listenbrainz import ListenBrainzPlugin


class TestListenBrainzPlugin(ConfigMixin):
    @pytest.fixture(scope="class")
    def plugin(self) -> ListenBrainzPlugin:
        self.config["listenbrainz"]["token"] = "test_token"
        self.config["listenbrainz"]["username"] = "test_user"
        return ListenBrainzPlugin()

    @pytest.mark.parametrize(
        "search_response, expected_id",
        [([{"id": "id1"}], "id1"), ([], None)],
        ids=["found", "not_found"],
    )
    def test_get_mb_recording_id(
        self, plugin, requests_mock, search_response, expected_id
    ):
        requests_mock.get(
            "/ws/2/recording", json={"recordings": search_response}
        )
        track = {"track_metadata": {"track_name": "S", "release_name": "A"}}

        assert plugin.get_mb_recording_id(track) == expected_id

    def test_get_track_info(self, plugin, requests_mock):
        requests_mock.get(
            "/ws/2/recording/id1?inc=releases%2Bartist-credits",
            json={
                "title": "T",
                "artist-credit": [],
                "releases": [{"title": "Al", "date": "2023-01"}],
            },
        )

        assert plugin.get_track_info([{"identifier": "id1"}]) == [
            {
                "identifier": "id1",
                "title": "T",
                "artist": None,
                "album": "Al",
                "year": "2023",
            }
        ]
