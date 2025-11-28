# This file is part of beets.
# Copyright 2016, Stig Inge Lea Bjornsen.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.


"""Tests for the `missing` plugin."""

import itertools
from unittest.mock import patch

import pytest

from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.library import Item
from beets.test.helper import (
    PluginMixin,
    TestHelper,
    capture_log,
    capture_stdout,
)


def mock_browse_release_groups(
    artist: str,
    release_type: list[str],
):
    """Helper to mock getting an artist's release groups of multiple release types."""
    release_groups = [
        {"id": "album_id", "title": "title", "release_type": "album"},
        {"id": "album2_id", "title": "title 2", "release_type": "album"},
        {
            "id": "compilation_id",
            "title": "compilation",
            "release_type": "compilation",
        },
    ]

    return {
        "release-group-list": [
            x for x in release_groups if x["release_type"] in release_type
        ]
    }


class TestMissingPlugin(PluginMixin, TestHelper):
    # The minimum mtime of the files to be imported
    plugin = "missing"

    def setup_method(self, method):
        """Setup pristine beets config and items for testing."""
        self.setup_beets()
        self.album_items = [
            Item(
                album="album",
                mb_albumid="81ae60d4-5b75-38df-903a-db2cfa51c2c6",
                mb_releasegroupid="album_id",
                mb_trackid="track_1",
                mb_albumartistid="f59c5520-ba9f-4df7-aa9f-90b46ef857da",
                albumartist="artist",
                tracktotal=3,
            ),
            Item(
                album="album",
                mb_albumid="81ae60d4-5b75-38df-903a-db2cfa51c2c6",
                mb_releasegroupid="album_id",
                mb_albumartistid="f59c5520-ba9f-4df7-aa9f-90b46ef857da",
                albumartist="artist",
                tracktotal=3,
            ),
            Item(
                album="album",
                mb_albumid="81ae60d4-5b75-38df-903a-db2cfa51c2c6",
                mb_releasegroupid="album_id",
                mb_trackid="track_3",
                mb_albumartistid="f59c5520-ba9f-4df7-aa9f-90b46ef857da",
                albumartist="artist",
                tracktotal=3,
            ),
        ]

    def teardown_method(self, method):
        """Clean all beets data."""
        self.teardown_beets()

    @pytest.mark.parametrize(
        "total,count",
        list(itertools.product((True, False), repeat=2)),
    )
    @patch("beets.metadata_plugins.album_for_id")
    def test_missing_tracks(self, album_for_id, total, count):
        """Test getting missing tracks works with expected logs."""
        self.lib.add_album(self.album_items[:2])

        album_for_id.return_value = AlbumInfo(
            album_id="album_id",
            album="album",
            tracks=[
                TrackInfo(track_id=album_item.mb_trackid)
                for album_item in self.album_items
            ],
        )

        command = ["missing"]
        if total:
            command.append("-t")
        if count:
            command.append("-c")

        if total:
            with capture_stdout() as output:
                self.run_command(*command)
            assert output.getvalue().strip() == "1"
        elif count:
            with capture_stdout() as output:
                self.run_command(*command)
            assert "artist - album: 1" in output.getvalue()
        else:
            with capture_log() as logs:
                self.run_command(*command)
            # The log message includes the "missing:" prefix in current master
            assert any(
                f"track {self.album_items[-1].mb_trackid} in album album_id"
                in log
                for log in logs
            )

    def test_missing_albums(self):
        """Test getting missing albums works with expected output."""
        with patch(
            "musicbrainzngs.browse_release_groups",
            wraps=mock_browse_release_groups,
        ):
            self.lib.add_album(self.album_items)

            with capture_stdout() as output:
                command = ["missing", "-a"]
                self.run_command(*command)

            output_str = output.getvalue()
            assert "artist - compilation" not in output_str
            assert "artist - title\n" not in output_str
            assert "artist - title 2" in output_str

    def test_missing_albums_compilation(self):
        """Test getting missing albums works for a specific release type."""
        with patch(
            "musicbrainzngs.browse_release_groups",
            wraps=mock_browse_release_groups,
        ):
            self.lib.add_album(self.album_items)

            with capture_stdout() as output:
                command = ["missing", "-a", "--release-type", "compilation"]
                self.run_command(*command)

            output_str = output.getvalue()
            assert "artist - compilation" in output_str
            assert "artist - title" not in output_str
            assert "artist - title 2" not in output_str

    def test_missing_albums_all(self):
        """Test getting missing albums works for all release types."""
        with patch(
            "musicbrainzngs.browse_release_groups",
            wraps=mock_browse_release_groups,
        ):
            self.lib.add_album(self.album_items)

            with capture_stdout() as output:
                command = [
                    "missing",
                    "-a",
                    "--release-type",
                    "compilation",
                    "--release-type",
                    "album",
                ]
                self.run_command(*command)

            output_str = output.getvalue()
            assert "artist - compilation" in output_str
            assert "artist - title\n" not in output_str
            assert "artist - title 2" in output_str

    def test_missing_albums_total(self):
        """Test getting missing albums works with the total flag."""
        with patch(
            "musicbrainzngs.browse_release_groups",
            wraps=mock_browse_release_groups,
        ):
            self.lib.add_album(self.album_items)

            with capture_stdout() as output:
                command = [
                    "missing",
                    "-a",
                    "-t",
                ]
                self.run_command(*command)

            output_str = output.getvalue().strip()
            assert output_str == "1"
            # Specific missing logs omitted if total provided
            assert "artist - compilation" not in output_str
            assert "artist - title" not in output_str
            assert "artist - title 2" not in output_str
