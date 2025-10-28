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

from beetsplug import fromfilename


class Session:
    pass


class Item:
    def __init__(self, path):
        self.path = path
        self.track = 0
        self.artist = ""
        self.title = ""


class Task:
    def __init__(self, items):
        self.items = items
        self.is_album = True


@pytest.mark.parametrize(
    "song1, song2",
    [
        (
            (
                "/tmp/01 - The Artist - Song One.m4a",
                1,
                "The Artist",
                "Song One",
            ),
            (
                "/tmp/02. - The Artist - Song Two.m4a",
                2,
                "The Artist",
                "Song Two",
            ),
        ),
        (
            ("/tmp/01-The_Artist-Song_One.m4a", 1, "The_Artist", "Song_One"),
            ("/tmp/02.-The_Artist-Song_Two.m4a", 2, "The_Artist", "Song_Two"),
        ),
        (
            ("/tmp/01 - Song_One.m4a", 1, "", "Song_One"),
            ("/tmp/02. - Song_Two.m4a", 2, "", "Song_Two"),
        ),
        (
            ("/tmp/Song One by The Artist.m4a", 0, "The Artist", "Song One"),
            ("/tmp/Song Two by The Artist.m4a", 0, "The Artist", "Song Two"),
        ),
        (("/tmp/01.m4a", 1, "", "01"), ("/tmp/02.m4a", 2, "", "02")),
        (
            ("/tmp/Song One.m4a", 0, "", "Song One"),
            ("/tmp/Song Two.m4a", 0, "", "Song Two"),
        ),
    ],
)
def test_fromfilename(song1, song2):
    """
    Each "song" is a tuple of path, expected track number, expected artist,
    expected title.

    We use two songs for each test for two reasons:
    - The plugin needs more than one item to look for uniform strings in paths
      in order to guess if the string describes an artist or a title.
    - Sometimes we allow for an optional "." after the track number in paths.
    """

    session = Session()
    item1 = Item(song1[0])
    item2 = Item(song2[0])
    task = Task([item1, item2])

    f = fromfilename.FromFilenamePlugin()
    f.filename_task(task, session)

    assert task.items[0].track == song1[1]
    assert task.items[0].artist == song1[2]
    assert task.items[0].title == song1[3]
    assert task.items[1].track == song2[1]
    assert task.items[1].artist == song2[2]
    assert task.items[1].title == song2[3]
