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

import pytest

from beets.library import Item, Library
from beets.ui.commands.stats import show_overview_report


# --- Fixtures ---
@pytest.fixture
def library(tmp_path):
    """Create a temporary empty Beets library."""
    lib_path = tmp_path / "beets.db"
    lib = Library(str(lib_path))
    return lib


def add_item(
    lib,
    title="Test",
    artist="Artist",
    album="Album",
    genre="Genre",
    year=2000,
    length=180,
    bitrate=320000,
    format="MP3",
):
    """Add a single Item to the test library."""
    item = Item(
        path=f"/tmp/{title}.mp3",
        title=title,
        artist=artist,
        album=album,
        genre=genre,
        year=year,
        length=length,
        bitrate=bitrate,
        format=format,
    )
    lib.add(item)


# --- Tests for show_overview_report ---


def test_empty_library_overview(capsys, library):
    """Test empty library with overview report."""
    show_overview_report(library, [])
    captured = capsys.readouterr()
    assert "Your Beets library is empty." in captured.out


def test_single_item_overview(capsys, library):
    """Test library with a single track using overview report."""

    add_item(
        library,
        title="Single Track",
        artist="Solo Artist",
        genre="Indie",
        year=2019,
        bitrate=256000,
    )

    show_overview_report(library, [])
    captured = capsys.readouterr()

    # --- Check basic statistics ---
    # Format is "Tracks:   X" (3 spaces after colon)
    assert "Tracks:   1" in captured.out
    assert "Albums:   1" in captured.out
    assert "Artists:  1" in captured.out
    assert "Genres:   1" in captured.out

    # --- Wrapped-style insights ---
    assert "Top artist:   Solo Artist (1 tracks)" in captured.out
    assert "Top genre:    Indie (1 tracks)" in captured.out

    # Decade format: "10s (2010-2019): 1 tracks (100.0%)"
    assert "10s (2010-2019" in captured.out
    assert "1 tracks" in captured.out

    # Year format
    assert "Top year:     2019 (1 tracks)" in captured.out


def test_multiple_items_overview(capsys, library):
    """Test library with multiple tracks using overview report."""

    # 1995 – 2 tracks Rock
    add_item(library, "Track1", "Artist A", "Album X", "Rock", 1995)
    add_item(library, "Track2", "Artist A", "Album X", "Rock", 1995)

    # 2002 – 1 track Pop
    add_item(library, "Track3", "Artist B", "Album Y", "Pop", 2002)

    # 2018 – 1 track Electronic
    add_item(library, "Track4", "Artist C", "Album Z", "Electronic", 2018)

    show_overview_report(library, [])
    captured = capsys.readouterr()

    # --- Basic stats ---
    assert "Tracks:   4" in captured.out
    assert "Albums:   3" in captured.out
    assert "Artists:  3" in captured.out
    assert "Genres:   3" in captured.out

    # --- Wrapped insights ---
    assert "Top artist:   Artist A (2 tracks)" in captured.out
    assert "Top genre:    Rock (2 tracks)" in captured.out

    # Decade format check
    assert "90s (1990-1999" in captured.out
    assert "2 tracks" in captured.out

    # Year format
    assert "Top year:     1995 (2 tracks)" in captured.out

    # --- Decade distribution ---
    assert "90s (1990-1999" in captured.out
    assert "00s (2000-2009" in captured.out
    assert "10s (2010-2019" in captured.out


def test_missing_metadata_overview(capsys, library):
    """Test library with missing tags using overview report."""

    # Missing genre
    add_item(
        library,
        "Track1",
        "Artist",
        "Album",
        None,
        2000,
        length=200,
        bitrate=256000,
    )
    # Missing year
    add_item(
        library,
        "Track2",
        "Artist",
        "Album",
        "Rock",
        None,
        length=180,
        bitrate=256000,
    )

    show_overview_report(library, [])
    captured = capsys.readouterr()

    # Format has 2 spaces after colon for year tags
    assert "Missing genre tags: 1" in captured.out
    assert "Missing year tags:  1" in captured.out


def test_various_lengths_and_bitrates_overview(capsys, library):
    """Test track lengths and bitrate classification."""

    add_item(library, "Short", "A", "X", "Pop", 2010, length=60, bitrate=128000)
    add_item(
        library, "Long", "B", "Y", "Rock", 2015, length=3600, bitrate=1024000
    )

    show_overview_report(library, [])
    captured = capsys.readouterr()

    # --- Check durations ---
    assert "Total playtime:" in captured.out
    assert "Avg track length:" in captured.out

    # --- Check bitrate and quality classification ---
    assert "Avg bitrate:" in captured.out
    assert "kbps" in captured.out
