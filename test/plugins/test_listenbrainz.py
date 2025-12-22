import pytest

from beets.test.helper import ConfigMixin
from beetsplug.listenbrainz import ListenBrainzPlugin


class TestListenBrainzPlugin(ConfigMixin):
    @pytest.fixture(scope="class")
    def plugin(self):
        self.config["listenbrainz"]["token"] = "test_token"
        self.config["listenbrainz"]["username"] = "test_user"
        return ListenBrainzPlugin()

    @pytest.mark.parametrize(
        "search_response, expected_id",
        [
            (
                {"recording-count": "1", "recording-list": [{"id": "id1"}]},
                "id1",
            ),
            ({"recording-count": "0"}, None),
        ],
        ids=["found", "not_found"],
    )
    def test_get_mb_recording_id(
        self, monkeypatch, plugin, search_response, expected_id
    ):
        monkeypatch.setattr(
            "musicbrainzngs.search_recordings", lambda *_, **__: search_response
        )
        track = {"track_metadata": {"track_name": "S", "release_name": "A"}}

        assert plugin.get_mb_recording_id(track) == expected_id

    def test_get_track_info(self, monkeypatch, plugin):
        monkeypatch.setattr(
            "musicbrainzngs.get_recording_by_id",
            lambda *_, **__: {
                "recording": {
                    "title": "T",
                    "artist-credit": [],
                    "release-list": [{"title": "Al", "date": "2023-01"}],
                }
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
