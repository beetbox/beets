import io
import json
import zipfile
from unittest.mock import patch

import pytest

from beets import ui
from beets.test.helper import ConfigMixin
from beetsplug.listenbrainz import ListenBrainzPlugin


def _make_zip(files: dict[str, str]) -> bytes:
    """Build an in-memory zip with the given {name: content} entries."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


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

    def test_aggregate_listens_counts_by_mbid(self, plugin):
        tracks = [
            {
                "mbid": "m1",
                "artist": "A",
                "name": "S",
                "album": "Al",
                "playcount": 1,
            },
            {
                "mbid": "m1",
                "artist": "A",
                "name": "S",
                "album": "Al",
                "playcount": 1,
            },
            {
                "mbid": "m1",
                "artist": "A",
                "name": "S",
                "album": "Al",
                "playcount": 1,
            },
            {
                "mbid": "m2",
                "artist": "B",
                "name": "T",
                "album": "Bl",
                "playcount": 1,
            },
        ]
        result = plugin._aggregate_listens(tracks)
        by_mbid = {t["mbid"]: t["playcount"] for t in result}
        assert by_mbid == {"m1": 3, "m2": 1}

    def test_aggregate_listens_falls_back_to_artist_title_album(self, plugin):
        tracks = [
            {
                "mbid": None,
                "artist": "A",
                "name": "S",
                "album": "Al",
                "playcount": 1,
            },
            {
                "mbid": "",
                "artist": "A",
                "name": "S",
                "album": "Al",
                "playcount": 1,
            },
            {
                "mbid": None,
                "artist": "A",
                "name": "S",
                "album": "Al",
                "playcount": 1,
            },
        ]
        result = plugin._aggregate_listens(tracks)
        assert len(result) == 1
        assert result[0]["playcount"] == 3

    def test_get_listens_paginates(self, plugin):
        page1 = [
            {
                "listened_at": 100 - i,
                "track_metadata": {
                    "track_name": f"T{i}",
                    "artist_name": "A",
                    "release_name": "R",
                },
            }
            for i in range(5)
        ]
        page2 = [
            {
                "listened_at": 50 - i,
                "track_metadata": {
                    "track_name": f"T{5 + i}",
                    "artist_name": "A",
                    "release_name": "R",
                },
            }
            for i in range(3)
        ]

        call_count = 0

        def mock_request(url, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"payload": {"listens": page1}}
            if call_count == 2:
                return {"payload": {"listens": page2}}
            return {"payload": {"listens": []}}

        with patch.object(plugin, "_make_request", side_effect=mock_request):
            result = plugin.get_listens(count=5)

        assert len(result) == 8
        assert call_count == 2

    def test_get_listens_stops_on_empty_page(self, plugin):
        def mock_request(url, params=None):
            return {"payload": {"listens": []}}

        with patch.object(plugin, "_make_request", side_effect=mock_request):
            result = plugin.get_listens()

        assert result == []

    def test_get_listens_returns_none_on_api_error(self, plugin):
        def mock_request(url, params=None):
            return None

        with patch.object(plugin, "_make_request", side_effect=mock_request):
            result = plugin.get_listens()

        assert result is None

    def test_get_listens_rejects_both_min_and_max_ts(self, plugin):
        with pytest.raises(ValueError, match="mutually exclusive"):
            plugin.get_listens(min_ts=1, max_ts=2)

    def test_get_listens_clamps_count_to_1000(self, plugin):
        calls = []

        def mock_request(url, params=None):
            calls.append(params)
            return {"payload": {"listens": []}}

        with patch.object(plugin, "_make_request", side_effect=mock_request):
            plugin.get_listens(count=5000)

        assert calls[0]["count"] == 1000

    def test_get_tracks_from_listens_uses_recording_mbid(self, plugin):
        listens = [
            {
                "listened_at": 1000,
                "track_metadata": {
                    "track_name": "Song",
                    "artist_name": "Artist",
                    "release_name": "Album",
                    "mbid_mapping": {
                        "recording_mbid": "rec-mbid-123",
                        "release_mbid": "rel-mbid",
                    },
                },
            }
        ]
        tracks = plugin.get_tracks_from_listens(listens)
        assert tracks[0]["mbid"] == "rec-mbid-123"
        assert tracks[0]["playcount"] == 1

    def test_get_tracks_from_listens_no_mbid_mapping(self, plugin):
        listens = [
            {
                "listened_at": 1000,
                "track_metadata": {
                    "track_name": "Song",
                    "artist_name": "Artist",
                    "release_name": "Album",
                },
            }
        ]
        tracks = plugin.get_tracks_from_listens(listens)
        assert tracks[0]["mbid"] is None

    def test_get_listens_respects_max_total(self, plugin):
        def mock_request(url, params=None):
            count = params.get("count", 5)
            return {
                "payload": {
                    "listens": [
                        {"listened_at": 100 - i, "track_metadata": {}}
                        for i in range(count)
                    ]
                }
            }

        with patch.object(plugin, "_make_request", side_effect=mock_request):
            result = plugin.get_listens(max_total=7)

        assert len(result) == 7

    def test_get_tracks_from_listens_flat_structure(self, plugin):
        listens = [
            {
                "listened_at": 1000,
                "track_metadata": {
                    "track_name": "Song",
                    "artist_name": "Artist",
                    "release_name": "Album",
                    "mbid_mapping": {"recording_mbid": "m1"},
                },
            }
        ]
        tracks = plugin.get_tracks_from_listens(listens)
        t = tracks[0]
        assert isinstance(t["artist"], str)
        assert isinstance(t["name"], str)
        assert t["album"] == "Album"

    def test_get_tracks_from_listens_null_mbid_mapping(self, plugin):
        listens = [
            {
                "listened_at": 1000,
                "track_metadata": {
                    "track_name": "Song",
                    "artist_name": "Artist",
                    "release_name": "Album",
                    "mbid_mapping": None,
                },
            }
        ]
        tracks = plugin.get_tracks_from_listens(listens)  # should not raise
        assert tracks[0]["mbid"] is None

    def test_get_tracks_from_listens_prefers_additional_info_recording_mbid(
        self, plugin
    ):
        listens = [
            {
                "listened_at": 1000,
                "track_metadata": {
                    "track_name": "Song",
                    "artist_name": "Artist",
                    "release_name": "Album",
                    "additional_info": {"recording_mbid": "rec-mbid-123"},
                    "mbid_mapping": {
                        "recording_mbid": "rec-mbid-456",
                        "release_mbid": "rel-mbid",
                    },
                },
            }
        ]
        tracks = plugin.get_tracks_from_listens(listens)
        assert tracks[0]["mbid"] == "rec-mbid-123"
        assert tracks[0]["playcount"] == 1

    def test_import_file_returns_listens(self, plugin, tmp_path):
        listen = {
            "listened_at": 1778946700,
            "track_metadata": {"track_name": "S"},
        }
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(
            _make_zip({"listens/2026.jsonl": json.dumps(listen) + "\n"})
        )

        result = plugin.import_listenbrainz_data_export(zip_path)

        assert result == [listen]

    def test_import_file_ignores_non_listens_entries(self, plugin, tmp_path):
        listen = {"listened_at": 1778946700, "track_metadata": {}}
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(
            _make_zip(
                {
                    "listens/2026.jsonl": json.dumps(listen) + "\n",
                    "other/data.jsonl": '{"should": "be ignored"}\n',
                    "listens/readme.txt": "not a jsonl file\n",
                }
            )
        )

        result = plugin.import_listenbrainz_data_export(zip_path)

        assert result == [listen]

    def test_import_file_skips_empty_lines(self, plugin, tmp_path):
        listen = {"listened_at": 1778946700, "track_metadata": {}}
        content = "\n" + json.dumps(listen) + "\n\n"
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip({"listens/2026.jsonl": content}))

        result = plugin.import_listenbrainz_data_export(zip_path)

        assert result == [listen]

    def test_import_file_skips_invalid_json(self, plugin, tmp_path):
        listen = {"listened_at": 1778946700, "track_metadata": {}}
        content = "not valid json\n" + json.dumps(listen) + "\n"
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip({"listens/2026.jsonl": content}))

        result = plugin.import_listenbrainz_data_export(zip_path)

        assert result == [listen]

    def test_import_file_raises_on_missing_file(self, plugin, tmp_path):
        with pytest.raises(ui.UserError):
            plugin.import_listenbrainz_data_export(tmp_path / "nonexistent.zip")
