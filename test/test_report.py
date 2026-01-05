import pytest
from beets.library import Item
from beetsplug.report import ReportPlugin


# --- Fixtures ---
@pytest.fixture
def library(tmp_path):
    """Create a temporary empty Beets library."""
    from beets.library import Library

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
    bitrate=320000,  # bitrate in bits per second
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


# --- Tests ---
def test_empty_library(capsys, library):
    """Test empty library: should output message without crashing."""
    plugin = ReportPlugin()
    plugin._run_report(library, None, [])
    captured = capsys.readouterr()
    assert "Your Beets library is empty." in captured.out


def test_single_item(capsys, library):
    """Test library with a single track, including bitrate/quality and format."""
    add_item(
        library,
        title="Single Track",
        artist="Solo Artist",
        genre="Indie",
        year=2019,
        length=240,
        bitrate=256000,  # 256 kbps
        format="MP3",
    )
    plugin = ReportPlugin()
    plugin._run_report(library, None, [])
    captured = capsys.readouterr()

    # --- Basic statistics ---
    assert "Tracks:" in captured.out
    assert "Albums:" in captured.out
    assert "Artists:" in captured.out
    assert "Genres:" in captured.out

    # --- Wrapped-style insights ---
    assert "Top artist:" in captured.out
    assert "Solo Artist" in captured.out
    assert "Top genre:" in captured.out
    assert "Indie" in captured.out
    assert "Top decade:" in captured.out
    assert "10s" in captured.out
    assert "Top year:" in captured.out
    assert "2019" in captured.out

    # --- Bitrate / quality ---
    avg_bitrate_lines = [
        line
        for line in captured.out.splitlines()
        if line.strip().startswith("Avg bitrate:")
    ]
    assert avg_bitrate_lines, "Expected an 'Avg bitrate:' line in output"
    avg_line = avg_bitrate_lines[0]
    assert "kbps" in avg_line
    assert "(" in avg_line and ")" in avg_line  # Quality label

    # --- Primary format ---
    primary_format_lines = [
        line
        for line in captured.out.splitlines()
        if line.strip().startswith("Primary format:")
    ]
    assert primary_format_lines, "Expected a 'Primary format:' line in output"
    primary_line = primary_format_lines[0]
    assert "MP3" in primary_line


def test_multiple_items(capsys, library):
    """Test library with multiple tracks from different decades and genres."""
    add_item(library, "Track1", "Artist A", "Album X", "Rock", 1995)
    add_item(library, "Track2", "Artist A", "Album X", "Rock", 1995)
    add_item(library, "Track3", "Artist B", "Album Y", "Pop", 2002)
    add_item(library, "Track4", "Artist C", "Album Z", "Electronic", 2018)

    plugin = ReportPlugin()
    plugin._run_report(library, None, [])
    captured = capsys.readouterr()

    # --- Basic stats ---
    assert "Tracks:" in captured.out
    assert "4" in captured.out
    assert "Albums:" in captured.out
    assert "3" in captured.out
    assert "Artists:" in captured.out
    assert "3" in captured.out
    assert "Genres:" in captured.out
    assert "3" in captured.out

    # --- Wrapped-style insights ---
    assert "Top artist:" in captured.out
    assert "Artist A" in captured.out
    assert "Top genre:" in captured.out
    assert "Rock" in captured.out
    assert "Top decade:" in captured.out
    assert "90s" in captured.out
    assert "Top year:" in captured.out
    assert "1995" in captured.out

    # --- Decade distribution ---
    assert "90s" in captured.out
    assert "00s" in captured.out
    assert "10s" in captured.out


def test_missing_metadata(capsys, library):
    """Test library with missing tags, length, and bitrate."""
    add_item(
        library,
        "Track1",
        "Artist",
        "Album",
        None,  # missing genre
        2000,
        length=200,
        bitrate=256000,
    )
    add_item(
        library,
        "Track2",
        "Artist",
        "Album",
        "Rock",
        None,  # missing year
        length=180,
        bitrate=None,
    )

    plugin = ReportPlugin()
    plugin._run_report(library, None, [])
    captured = capsys.readouterr()

    # --- Check missing metadata counts ---
    lines = captured.out.splitlines()

    # Check for missing genre
    genre_found = False
    for line in lines:
        if "Missing genre tags:" in line:
            assert "1" in line
            genre_found = True
            break
    assert genre_found

    # Check for missing year
    year_found = False
    for line in lines:
        if "Missing year tags:" in line:
            assert "1" in line
            year_found = True
            break
    assert year_found
