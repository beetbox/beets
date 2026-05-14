# This file is part of beets.
# Copyright 2016, Thomas Scholtes.
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

from unittest.mock import Mock, patch

import pytest

from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.library import Item
from beets.test.helper import PluginMixin, TestHelper


class PytestPluginTestHelper(PluginMixin, TestHelper):
    """Same as the BeetsTestCase unittest setup but for pytest."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.setup_beets()
        try:
            yield
        finally:
            self.teardown_beets()


class TestMbsyncCli(PytestPluginTestHelper):
    plugin = "mbsync"

    @patch(
        "beets.metadata_plugins.album_for_id",
        Mock(
            side_effect=lambda *_: AlbumInfo(
                album_id="album id",
                album="new album",
                tracks=[TrackInfo(track_id="track id", title="new title")],
            )
        ),
    )
    @patch(
        "beets.metadata_plugins.track_for_id",
        Mock(
            side_effect=lambda *_: TrackInfo(
                track_id="singleton id", title="new title"
            )
        ),
    )
    def test_update_library(self):
        album_item = Item(
            album="old album",
            mb_albumid="album id",
            mb_trackid="track id",
            data_source="data_source",
        )
        self.lib.add_album([album_item])

        singleton = Item(
            title="old title",
            mb_trackid="singleton id",
            data_source="data_source",
        )
        self.lib.add(singleton)

        self.run_command("mbsync")

        singleton.load()
        assert singleton.title == "new title"

        album_item.load()
        assert album_item.title == "new title"
        assert album_item.mb_trackid == "track id"
        assert album_item.get_album().album == "new album"

    def test_custom_format(self, caplog):
        for item in [
            Item(artist="albumartist", album="no id"),
            Item(
                artist="albumartist",
                album="invalid id",
                mb_albumid="a1b2c3d4",
            ),
        ]:
            self.lib.add_album([item])

        for item in [
            Item(artist="artist", title="no id"),
            Item(artist="artist", title="invalid id", mb_trackid="a1b2c3d4"),
        ]:
            self.lib.add(item)

        with caplog.at_level("DEBUG", logger="beets.mbsync"):
            self.run_command("mbsync", "-f", "'%if{$album,$album,$title}'")

        assert (
            "mbsync: Skipping album with no mb_albumid: 'no id'"
            in caplog.messages
        )
        assert (
            "mbsync: Skipping singleton with no mb_trackid: 'no id'"
            in caplog.messages
        )

    @patch(
        "beets.metadata_plugins.album_for_id",
        Mock(
            side_effect=lambda *_: AlbumInfo(
                album_id="album id",
                album="new album",
                tracks=[TrackInfo(track_id="track id", title="new title")],
            )
        ),
    )
    @patch(
        "beets.metadata_plugins.track_for_id",
        Mock(
            side_effect=lambda *_: TrackInfo(
                track_id="singleton id", title="new title"
            )
        ),
    )
    def test_update_library_from_scratch_set(self):
        self.config["import"]["from_scratch"] = True

        test_lyrics = "Hello"

        album_item = Item(
            album="old album",
            mb_albumid="album id",
            mb_trackid="track id",
            data_source="data_source",
            lyrics=test_lyrics,
        )
        self.lib.add_album([album_item])

        singleton = Item(
            title="old title",
            mb_trackid="singleton id",
            data_source="data_source",
            lyrics=test_lyrics,
        )
        self.lib.add(singleton)

        self.run_command("mbsync")

        singleton.load()
        assert singleton.lyrics == test_lyrics

        album_item.load()
        assert album_item.lyrics == test_lyrics
