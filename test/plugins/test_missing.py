"""Tests for the `missing` plugin."""

import re
import uuid
from unittest.mock import patch

import pytest

from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.library import Album, Item
from beets.test.helper import IOMixin, PluginMixin, TestHelper


@pytest.fixture
def helper(request):
    helper = TestHelper()
    helper.setup_beets()

    request.instance.lib = helper.lib

    yield

    helper.teardown_beets()


@pytest.mark.usefixtures("helper")
class TestMissingAlbums(IOMixin, PluginMixin):
    """Tests for missing albums functionality."""

    plugin = "missing"

    @pytest.mark.parametrize(
        "release_from_mb,expected_output",
        [
            pytest.param(
                {"id": "other", "title": "Other Album"},
                "Artist - Other Album\n",
                id="missing",
            ),
            pytest.param(
                {"id": "release_group_in_lib", "title": "Album"},
                "",
                id="not missing",
            ),
        ],
    )
    def test_missing_artist_albums(
        self, requests_mock, release_from_mb, expected_output
    ):
        artist_mbid = str(uuid.uuid4())
        self.lib.add(
            Album(
                album="Album",
                albumartist="Artist",
                mb_albumartistid=artist_mbid,
                mb_albumid="album",
                mb_releasegroupid="release_group_in_lib",
            )
        )
        requests_mock.get(
            re.compile(
                rf"/ws/2/release-group\?artist={artist_mbid}&.*type=album"
            ),
            json={"release-groups": [release_from_mb]},
        )

        with self.configure_plugin({}):
            assert self.run_with_output("missing", "--album") == expected_output

    def test_release_types_filters_results(self, requests_mock):
        """Test --release-types filters to only show specified type."""
        artist_mbid = str(uuid.uuid4())
        self.lib.add(
            Album(
                album="album",
                albumartist="artist",
                mb_albumartistid=artist_mbid,
                mb_albumid="album",
                mb_releasegroupid="album_id",
            )
        )
        requests_mock.get(
            re.compile(r"/ws/2/release-group.*type=compilation"),
            json={
                "release-groups": [
                    {"id": "compilation_id", "title": "compilation"}
                ]
            },
        )

        with self.configure_plugin({}):
            output = self.run_with_output(
                "missing", "-a", "--release-types", "compilation"
            )

        assert "artist - compilation" in output

    def test_release_types_comma_separated(self, requests_mock):
        """Test --release-types with comma-separated values."""
        artist_mbid = str(uuid.uuid4())
        self.lib.add(
            Album(
                album="album",
                albumartist="artist",
                mb_albumartistid=artist_mbid,
                mb_albumid="album",
                mb_releasegroupid="album_id",
            )
        )
        requests_mock.get(
            re.compile(r"/ws/2/release-group.*type=compilation%7Calbum"),
            json={
                "release-groups": [
                    {"id": "album2_id", "title": "title 2"},
                    {"id": "compilation_id", "title": "compilation"},
                ]
            },
        )

        with self.configure_plugin({}):
            output = self.run_with_output(
                "missing",
                "-a",
                "--release-types",
                "compilation,album",
            )

        assert "artist - compilation" in output
        assert "artist - title 2" in output

    def test_empty_release_types_config_sends_empty_type(self, requests_mock):
        """Test that release_types: [] in config sends type="" to the API."""
        artist_mbid = str(uuid.uuid4())
        self.lib.add(
            Album(
                album="album",
                albumartist="artist",
                mb_albumartistid=artist_mbid,
                mb_albumid="album",
                mb_releasegroupid="album_id",
            )
        )
        adapter = requests_mock.get(
            re.compile(r"/ws/2/release-group"),
            json={"release-groups": []},
        )

        with self.configure_plugin({"release_types": []}):
            self.run_with_output("missing", "-a")

        assert adapter.last_request.qs["type"] == [""]

    def test_missing_albums_total(self, requests_mock):
        """Test -t flag with --album shows total count of missing albums."""
        artist_mbid = str(uuid.uuid4())
        self.lib.add(
            Album(
                album="album",
                albumartist="artist",
                mb_albumartistid=artist_mbid,
                mb_albumid="album",
                mb_releasegroupid="album_id",
            )
        )
        requests_mock.get(
            re.compile(
                rf"/ws/2/release-group\?artist={artist_mbid}&.*type=album"
            ),
            json={
                "release-groups": [
                    {"id": "album_id", "title": "album"},
                    {"id": "other_id", "title": "other"},
                ]
            },
        )

        with self.configure_plugin({}):
            output = self.run_with_output("missing", "-a", "-t")

        assert output == "1\n"


@pytest.mark.usefixtures("helper")
class TestMissingTracks(IOMixin, PluginMixin):
    """Tests for missing tracks functionality."""

    plugin = "missing"

    @pytest.mark.parametrize(
        "total,count,expected",
        [
            (True, False, "1\n"),
            (False, True, "artist - album: 1"),
        ],
    )
    @patch("beets.metadata_plugins.album_for_id")
    def test_missing_tracks(self, album_for_id, total, count, expected):
        """Test getting missing tracks works with expected output."""
        artist_mbid = str(uuid.uuid4())
        album_items = [
            Item(
                album="album",
                mb_albumid="81ae60d4-5b75-38df-903a-db2cfa51c2c6",
                mb_releasegroupid="album_id",
                mb_trackid="track_1",
                mb_albumartistid=artist_mbid,
                albumartist="artist",
                tracktotal=3,
            ),
            Item(
                album="album",
                mb_albumid="81ae60d4-5b75-38df-903a-db2cfa51c2c6",
                mb_releasegroupid="album_id",
                mb_albumartistid=artist_mbid,
                albumartist="artist",
                tracktotal=3,
            ),
            Item(
                album="album",
                mb_albumid="81ae60d4-5b75-38df-903a-db2cfa51c2c6",
                mb_releasegroupid="album_id",
                mb_trackid="track_3",
                mb_albumartistid=artist_mbid,
                albumartist="artist",
                tracktotal=3,
            ),
        ]
        self.lib.add_album(album_items[:2])

        album_for_id.return_value = AlbumInfo(
            album_id="album_id",
            album="album",
            tracks=[
                TrackInfo(track_id=item.mb_trackid) for item in album_items
            ],
        )

        command = ["missing"]
        if total:
            command.append("-t")
        if count:
            command.append("-c")

        with self.configure_plugin({}):
            assert expected in self.run_with_output(*command)
