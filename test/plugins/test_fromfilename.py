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

import pytest

from beets.importer.tasks import ImportTask, SingletonImportTask
from beets.library import Item
from beets.test.helper import PluginMixin
from beetsplug.fromfilename import FilenameMatch, FromFilenamePlugin


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


def mock_task(items):
    return ImportTask(toppath=None, paths=None, items=items)


@pytest.mark.parametrize(
    "text,matchgroup",
    [
        ("3", FilenameMatch({"track": "3", "title": "3"})),
        ("04", FilenameMatch({"track": "04", "title": "04"})),
        ("6.", FilenameMatch({"track": "6", "title": "6"})),
        ("3.5", FilenameMatch({"disc": "3", "track": "5"})),
        ("1-02", FilenameMatch({"disc": "1", "track": "02"})),
        ("100-4", FilenameMatch({"disc": "100", "track": "4"})),
        (
            "04.Title",
            FilenameMatch({"track": "04", "title": "Title"}),
        ),
        (
            "5_-_Title",
            FilenameMatch({"track": "5", "title": "Title"}),
        ),
        (
            "1-02 Title",
            FilenameMatch({"disc": "1", "track": "02", "title": "Title"}),
        ),
        (
            "3.5 - Title",
            FilenameMatch({"disc": "3", "track": "5", "title": "Title"}),
        ),
        (
            "5_-_Artist_-_Title",
            FilenameMatch({"track": "5", "artist": "Artist", "title": "Title"}),
        ),
        (
            "3-8- Artist-Title",
            FilenameMatch(
                {
                    "disc": "3",
                    "track": "8",
                    "artist": "Artist",
                    "title": "Title",
                }
            ),
        ),
        (
            "4-3 - Artist Name - Title",
            FilenameMatch(
                {
                    "disc": "4",
                    "track": "3",
                    "artist": "Artist Name",
                    "title": "Title",
                }
            ),
        ),
        (
            "4-3_-_Artist_Name_-_Title",
            FilenameMatch(
                {
                    "disc": "4",
                    "track": "3",
                    "artist": "Artist_Name",
                    "title": "Title",
                }
            ),
        ),
        (
            "6 Title by Artist",
            FilenameMatch({"track": "6", "artist": "Artist", "title": "Title"}),
        ),
        (
            "Title",
            FilenameMatch({"title": "Title"}),
        ),
    ],
)
def test_parse_track_info(text, matchgroup):
    f = FromFilenamePlugin()
    m = f._parse_track_info(text)
    assert dict(matchgroup.items()) == dict(m.items())


@pytest.mark.parametrize(
    "text,matchgroup",
    [
        (
            # highly unlikely
            "",
            FilenameMatch(
                {
                    "albumartist": None,
                    "album": None,
                    "year": None,
                    "catalognum": None,
                    "media": None,
                }
            ),
        ),
        (
            "1970",
            FilenameMatch(
                {
                    "year": "1970",
                }
            ),
        ),
        (
            "Album Title",
            FilenameMatch(
                {
                    "album": "Album Title",
                }
            ),
        ),
        (
            "Artist - Album Title",
            FilenameMatch(
                {
                    "albumartist": "Artist",
                    "album": "Album Title",
                }
            ),
        ),
        (
            "Artist - Album Title (2024)",
            FilenameMatch(
                {
                    "albumartist": "Artist",
                    "album": "Album Title",
                    "year": "2024",
                }
            ),
        ),
        (
            "Artist - 2024 - Album Title [flac]",
            FilenameMatch(
                {
                    "albumartist": "Artist",
                    "album": "Album Title",
                    "year": "2024",
                }
            ),
        ),
        (
            "(2024) Album Title [CATALOGNUM] WEB",
            # sometimes things are just going to be unparsable
            FilenameMatch(
                {
                    "albumartist": "Album Title",
                    "album": "WEB",
                    "year": "2024",
                    "catalognum": "CATALOGNUM",
                }
            ),
        ),
        (
            "{2024} Album Artist - Album Title [INFO-WAV]",
            FilenameMatch(
                {
                    "albumartist": "Album Artist",
                    "album": "Album Title",
                    "year": "2024",
                }
            ),
        ),
        (
            "VA - Album Title [2025] [CD-FLAC]",
            FilenameMatch(
                {
                    "albumartist": "Various Artists",
                    "album": "Album Title",
                    "year": "2025",
                    "media": "CD",
                }
            ),
        ),
        (
            "Artist - Album Title 3000 (1998) [FLAC] {CATALOGNUM}",
            FilenameMatch(
                {
                    "albumartist": "Artist",
                    "album": "Album Title 3000",
                    "year": "1998",
                    "catalognum": "CATALOGNUM",
                }
            ),
        ),
        (
            "various - cd album (2023) [catalognum 123] {vinyl mp3}",
            FilenameMatch(
                {
                    "albumartist": "Various Artists",
                    "album": "cd album",
                    "year": "2023",
                    "catalognum": "catalognum 123",
                    "media": "Vinyl",
                }
            ),
        ),
        (
            "[CATALOG567] Album - Various (2020) [WEB-FLAC]",
            FilenameMatch(
                {
                    "albumartist": "Various Artists",
                    "album": "Album",
                    "year": "2020",
                    "catalognum": "CATALOG567",
                    "media": "Digital Media",
                }
            ),
        ),
        (
            "Album 3000 {web}",
            FilenameMatch(
                {
                    "album": "Album 3000",
                    "media": "Digital Media",
                }
            ),
        ),
    ],
)
def test_parse_album_info(text, matchgroup):
    f = FromFilenamePlugin()
    m = f._parse_album_info(text)
    assert matchgroup == m


@pytest.mark.parametrize(
    "string,pattern",
    [
        (
            "$albumartist - $album ($year)  {$comments}",
            r"(?P<albumartist>.+)\ \-\ (?P<album>.+)\ \((?P<year>.+)\)\ \ \{(?P<comments>.+)\}",
        ),
        ("$", None),
    ],
)
def test_parse_user_pattern_strings(string, pattern):
    f = FromFilenamePlugin()
    assert f._parse_user_pattern_strings(string) == pattern


class TestFromFilename(PluginMixin):
    plugin = "fromfilename"

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
        task = mock_task(items=[mock_item(path=expected_item.path)])
        f = FromFilenamePlugin()
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

    @pytest.mark.parametrize(
        "expected_items",
        [
            [
                mock_item(
                    path="/Artist - Album/01 - Track1 - Performer.flac",
                    track=1,
                    title="Track1",
                    album="Album",
                    albumartist="Artist",
                    artist="Performer",
                ),
                mock_item(
                    path="/Artist - Album/02 - Track2 - Artist.flac",
                    track=2,
                    title="Track2",
                    album="Album",
                    albumartist="Artist",
                    artist="Artist",
                ),
            ],
            [
                mock_item(
                    path=(
                        "/DiY - 8 Definitions of Bounce/"
                        "01 - Essa - Definition of Bounce.flac"
                    ),
                    track=1,
                    title="Definition of Bounce",
                    albumartist="DiY",
                    album="8 Definitions of Bounce",
                    artist="Essa",
                ),
                mock_item(
                    path=(
                        "/DiY - 8 Definitions of Bounce/"
                        "02 - Digs - Definition of Bounce.flac"
                    ),
                    track=2,
                    title="Definition of Bounce",
                    album="8 Definitions of Bounce",
                    albumartist="DiY",
                    artist="Digs",
                ),
            ],
            [
                mock_item(
                    path=("/Essa - Magneto Essa/1 - Essa - Magneto Essa.flac"),
                    track=1,
                    title="Magneto Essa",
                    album="Magneto Essa",
                    albumartist="Essa",
                    artist="Essa",
                ),
                mock_item(
                    path=("/Essa - Magneto Essa/2 - Essa - The Immortals.flac"),
                    track=2,
                    title="The Immortals",
                    album="Magneto Essa",
                    albumartist="Essa",
                    artist="Essa",
                ),
            ],
            [
                mock_item(
                    path=("/Magneto Essa/1 - Magneto Essa - Essa.flac"),
                    track=1,
                    title="Magneto Essa",
                    album="Magneto Essa",
                    artist="Essa",
                ),
                mock_item(
                    path=("/Magneto Essa/2 - The Immortals - Essa.flac"),
                    track=2,
                    title="The Immortals",
                    album="Magneto Essa",
                    artist="Essa",
                ),
            ],
            [
                # Even though it might be clear to human eyes,
                # we can't guess since the various flag is thrown
                mock_item(
                    path=(
                        "/Various - 303 Alliance 012/"
                        "1 - The End of Satellite - Benji303.flac"
                    ),
                    track=1,
                    title="Benji303",
                    album="303 Alliance 012",
                    artist="The End of Satellite",
                    albumartist="Various Artists",
                ),
                mock_item(
                    path=(
                        "/Various - 303 Alliance 012/"
                        "2 - Ruff Beats - Benji303.flac"
                    ),
                    track=2,
                    title="Benji303",
                    album="303 Alliance 012",
                    artist="Ruff Beats",
                    albumartist="Various Artists",
                ),
            ],
            [
                # Even though it might be clear to human eyes,
                # we can't guess since the various flag is thrown
                mock_item(
                    path=(
                        "/303 Alliance 012/"
                        "1 - The End of Satellite - Benji303.flac"
                    ),
                    track=1,
                    title="Benji303",
                    album="303 Alliance 012",
                    artist="The End of Satellite",
                ),
                mock_item(
                    path=(
                        "/303 Alliance 012/"
                        "2 - Ruff Beats - Benji303 & Sam J.flac"
                    ),
                    track=2,
                    title="Benji303 & Sam J",
                    album="303 Alliance 012",
                    artist="Ruff Beats",
                ),
            ],
        ],
    )
    def test_sanity_check(self, expected_items):
        """
        Take a list of expected items, create a task with just the paths.

        Goal is to ensure that sanity check
        correctly adjusts the parsed artists and albums

        After parsing, compare to the expected items.
        """
        task = mock_task([mock_item(path=item.path) for item in expected_items])
        f = FromFilenamePlugin()
        f.filename_task(task, Session())
        res = task.items
        exp = expected_items
        assert res[0].path == exp[0].path
        assert res[0].artist == exp[0].artist
        assert res[0].albumartist == exp[0].albumartist
        assert res[0].disc == exp[0].disc
        assert res[0].catalognum == exp[0].catalognum
        assert res[0].year == exp[0].year
        assert res[0].title == exp[0].title
        assert res[1].path == exp[1].path
        assert res[1].artist == exp[1].artist
        assert res[1].albumartist == exp[1].albumartist
        assert res[1].disc == exp[1].disc
        assert res[1].catalognum == exp[1].catalognum
        assert res[1].year == exp[1].year
        assert res[1].title == exp[1].title

    def test_singleton_import(self):
        task = SingletonImportTask(
            toppath=None, item=mock_item(path="/01 Track.wav")
        )
        f = FromFilenamePlugin()
        f.filename_task(task, Session())
        assert task.item.track == 1
        assert task.item.title == "Track"

    # TODO: Test with items that already have data, or other types of bad data.

    # TODO: Test with items that have perfectly fine data for the most part

    @pytest.mark.parametrize(
        "fields,expected",
        [
            (
                [
                    "albumartist",
                    "album",
                    "year",
                    "media",
                    "catalognum",
                    "artist",
                    "track",
                    "disc",
                    "title",
                ],
                mock_item(
                    albumartist="Album Artist",
                    album="Album",
                    year="2025",
                    media="CD",
                    catalognum="CATALOGNUM",
                    disc=1,
                    track=2,
                    artist="Artist",
                    title="Track",
                ),
            ),
            (
                ["album", "year", "media", "track", "disc", "title"],
                mock_item(
                    album="Album",
                    year="2025",
                    media="CD",
                    disc=1,
                    title="Track",
                ),
            ),
        ],
    )
    def test_fields(self, fields, expected):
        """
        With a set item and changing list of fields

        After parsing, compare to the original with the expected attributes defined.
        """
        path = (
            "/Album Artist - Album (2025) [FLAC CD] {CATALOGNUM}/"
            "1-2 Artist - Track.wav"
        )
        task = mock_task([mock_item(path=path)])
        expected.path = path
        with self.configure_plugin({"fields": fields}):
            f = FromFilenamePlugin()
            f.filename_task(task, Session())
            res = task.items[0]
            assert res.path == expected.path
            assert res.artist == expected.artist
            assert res.albumartist == expected.albumartist
            assert res.disc == expected.disc
            assert res.catalognum == expected.catalognum
            assert res.year == expected.year
            assert res.title == expected.title

    @pytest.mark.parametrize(
        "patterns,expected",
        [
            (
                {
                    "folder": ["($comments) - {$albumartist} - {$album}"],
                    "file": ["$artist - $track - $title"],
                },
                mock_item(
                    path="/(Comment) - {Album Artist} - {Album}/Artist - 02 - Title.flac",
                    comments="Comment",
                    albumartist="Album Artist",
                    album="Album",
                    artist="Artist",
                    track=2,
                    title="Title",
                ),
            ),
            (
                {
                    "folder": ["[$comments] - {$albumartist} - {$album}"],
                    "file": ["$artist - $track - $title"],
                },
                mock_item(
                    path="/(Comment) - {Album Artist} - {Album}/Artist - 02 - Title.flac",
                    artist="Artist",
                    track=2,
                    title="Title",
                    catalognum="Comment",
                ),
            ),
        ],
    )
    def test_user_patterns(self, patterns, expected):
        task = mock_task([mock_item(path=expected.path)])
        with self.configure_plugin({"patterns": patterns}):
            f = FromFilenamePlugin()
            f.filename_task(task, Session())
            res = task.items[0]
            assert res.comments == expected.comments
            assert res.path == expected.path
            assert res.artist == expected.artist
            assert res.albumartist == expected.albumartist
            assert res.disc == expected.disc
            assert res.catalognum == expected.catalognum
            assert res.year == expected.year
            assert res.title == expected.title

    def test_escape(self):
        assert FromFilenamePlugin._escape("{text}") == "{{text}}"
