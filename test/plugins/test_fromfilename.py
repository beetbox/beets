# This file is part of beets.
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

"""Tests for the fromfilename plugin."""

from dataclasses import dataclass

import pytest

from beets.library import Item
from beets.test.helper import ConfigMixin
from beetsplug import fromfilename


class Session:
    pass


def mock_item(**kwargs):
    defaults = dict(
        title="",
        artist="",
        albumartist="",
        album="",
        disc=0,
        track=0,
        catalognum="",
        media="",
        mtime=12345,
    )
    return Item(**{**defaults, **kwargs})


@dataclass
class Task:
    items: list[Item]
    is_album: bool = True


@pytest.mark.parametrize(
    "text,matchgroup",
    [
        ("3", {"disc": None, "track": "3", "artist": None, "title": "3"}),
        ("04", {"disc": None, "track": "04", "artist": None, "title": "04"}),
        ("6.", {"disc": None, "track": "6", "artist": None, "title": "6"}),
        ("3.5", {"disc": "3", "track": "5", "artist": None, "title": None}),
        ("1-02", {"disc": "1", "track": "02", "artist": None, "title": None}),
        ("100-4", {"disc": "100", "track": "4", "artist": None, "title": None}),
        (
            "04.Title",
            {"disc": None, "track": "04", "artist": None, "title": "Title"},
        ),
        (
            "5_-_Title",
            {"disc": None, "track": "5", "artist": None, "title": "Title"},
        ),
        (
            "1-02 Title",
            {"disc": "1", "track": "02", "artist": None, "title": "Title"},
        ),
        (
            "3.5 - Title",
            {"disc": "3", "track": "5", "artist": None, "title": "Title"},
        ),
        (
            "5_-_Artist_-_Title",
            {"disc": None, "track": "5", "artist": "Artist", "title": "Title"},
        ),
        (
            "3-8- Artist-Title",
            {"disc": "3", "track": "8", "artist": "Artist", "title": "Title"},
        ),
        (
            "4-3 - Artist Name - Title",
            {
                "disc": "4",
                "track": "3",
                "artist": "Artist Name",
                "title": "Title",
            },
        ),
        (
            "4-3_-_Artist_Name_-_Title",
            {
                "disc": "4",
                "track": "3",
                "artist": "Artist_Name",
                "title": "Title",
            },
        ),
        (
            "6 Title by Artist",
            {"disc": None, "track": "6", "artist": "Artist", "title": "Title"},
        ),
        (
            "Title",
            {"disc": None, "track": None, "artist": None, "title": "Title"},
        ),
    ],
)
def test_parse_track_info(text, matchgroup):
    f = fromfilename.FromFilenamePlugin()
    m = f.parse_track_info(text)
    assert matchgroup == m


@pytest.mark.parametrize(
    "text,matchgroup",
    [
        (
            # highly unlikely
            "",
            {
                "albumartist": None,
                "album": None,
                "year": None,
                "catalognum": None,
                "media": None,
            },
        ),
        (
            "1970",
            {
                "albumartist": None,
                "album": None,
                "year": "1970",
                "catalognum": None,
                "media": None,
            },
        ),
        (
            "Album Title",
            {
                "albumartist": None,
                "album": "Album Title",
                "year": None,
                "catalognum": None,
                "media": None,
            },
        ),
        (
            "Artist - Album Title",
            {
                "albumartist": "Artist",
                "album": "Album Title",
                "year": None,
                "catalognum": None,
                "media": None,
            },
        ),
        (
            "Artist - Album Title (2024)",
            {
                "albumartist": "Artist",
                "album": "Album Title",
                "year": "2024",
                "catalognum": None,
                "media": None,
            },
        ),
        (
            "Artist - 2024 - Album Title [flac]",
            {
                "albumartist": "Artist",
                "album": "Album Title",
                "year": "2024",
                "catalognum": None,
                "media": None,
            },
        ),
        (
            "(2024) Album Title [CATALOGNUM] WEB",
            # sometimes things are just going to be unparsable
            {
                "albumartist": "Album Title",
                "album": "WEB",
                "year": "2024",
                "catalognum": "CATALOGNUM",
                "media": None,
            },
        ),
        (
            "{2024} Album Artist - Album Title [INFO-WAV]",
            {
                "albumartist": "Album Artist",
                "album": "Album Title",
                "year": "2024",
                "catalognum": None,
                "media": None,
            },
        ),
        (
            "VA - Album Title [2025] [CD-FLAC]",
            {
                "albumartist": "Various Artists",
                "album": "Album Title",
                "year": "2025",
                "catalognum": None,
                "media": "CD",
            },
        ),
        (
            "Artist - Album Title 3000 (1998) [FLAC] {CATALOGNUM}",
            {
                "albumartist": "Artist",
                "album": "Album Title 3000",
                "year": "1998",
                "catalognum": "CATALOGNUM",
                "media": None,
            },
        ),
        (
            "various - cd album (2023) [catalognum 123] {vinyl mp3}",
            {
                "albumartist": "Various Artists",
                "album": "cd album",
                "year": "2023",
                "catalognum": "catalognum 123",
                "media": "Vinyl",
            },
        ),
        (
            "[CATALOG567] Album - Various (2020) [WEB-FLAC]",
            {
                "albumartist": "Various Artists",
                "album": "Album",
                "year": "2020",
                "catalognum": "CATALOG567",
                "media": "Digital Media",
            },
        ),
        (
            "Album 3000 {web}",
            {
                "albumartist": None,
                "album": "Album 3000",
                "year": None,
                "catalognum": None,
                "media": "Digital Media",
            },
        ),
    ],
)
def test_parse_album_info(text, matchgroup):
    f = fromfilename.FromFilenamePlugin()
    m = f.parse_album_info(text)
    assert matchgroup == m


class TestFromFilename(ConfigMixin):
    @pytest.mark.parametrize(
        "expected_item",
        [
            mock_item(
                path="/tmp/01 - The Artist - Song One.m4a",
                artist="The Artist",
                track=1,
                title="Song One",
            ),
            mock_item(
                path="/tmp/01 The Artist - Song One.m4a",
                artist="The Artist",
                track=1,
                title="Song One",
            ),
            mock_item(
                path="/tmp/02 The Artist - Song Two.m4a",
                artist="The Artist",
                track=2,
                title="Song Two",
            ),
            mock_item(
                path="/tmp/01-The_Artist-Song_One.m4a",
                artist="The_Artist",
                track=1,
                title="Song_One",
            ),
            mock_item(
                path="/tmp/02.-The_Artist-Song_Two.m4a",
                artist="The_Artist",
                track=2,
                title="Song_Two",
            ),
            mock_item(
                path="/tmp/01 - Song_One.m4a",
                track=1,
                title="Song_One",
            ),
            mock_item(
                path="/tmp/02. - Song_Two.m4a",
                track=2,
                title="Song_Two",
            ),
            mock_item(
                path="/tmp/Song One by The Artist.m4a",
                artist="The Artist",
                title="Song One",
            ),
            mock_item(
                path="/tmp/Song Two by The Artist.m4a",
                artist="The Artist",
                title="Song Two",
            ),
            mock_item(
                path="/tmp/01.m4a",
                track=1,
                title="01",
            ),
            mock_item(
                path="/tmp/02.m4a",
                track=2,
                title="02",
            ),
            mock_item(
                path="/tmp/Song One.m4a",
                title="Song One",
            ),
            mock_item(
                path="/tmp/Song Two.m4a",
                title="Song Two",
            ),
            mock_item(
                path=(
                    "/tmp/"
                    "[CATALOG567] Album - Various - [WEB-FLAC]"
                    "/2-10 - Artist - Song One.m4a"
                ),
                album="Album",
                artist="Artist",
                track=10,
                disc=2,
                albumartist="Various Artists",
                catalognum="CATALOG567",
                title="Song One",
                media="Digital Media",
            ),
            mock_item(
                path=(
                    "/tmp/"
                    "[CATALOG567] Album - Various - [WEB-FLAC]"
                    "/03-04 - Other Artist - Song Two.m4a"
                ),
                album="Album",
                artist="Other Artist",
                disc=3,
                track=4,
                albumartist="Various Artists",
                catalognum="CATALOG567",
                title="Song Two",
                media="Digital Media",
            ),
        ],
    )
    def test_fromfilename(self, expected_item):
        """
        Take expected items, create a task with just the paths.

        After parsing, compare to the original with the expected attributes defined.
        """
        task = Task([mock_item(path=expected_item.path)])
        f = fromfilename.FromFilenamePlugin()
        f.filename_task(task, Session())
        res = task.items[0]
        exp = expected_item
        assert res.path == exp.path
        assert res.artist == exp.artist
        assert res.albumartist == exp.albumartist
        assert res.disc == exp.disc
        assert res.catalognum == exp.catalognum
        assert res.year == exp.year
        assert res.title == exp.title
