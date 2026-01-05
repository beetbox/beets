import pytest
from beets.library import Item
from beetsplug.report_plugin import ReportPlugin

# --- Fixtures ---

@pytest.fixture
def library(tmp_path):
    """Create a temporary empty Beets library."""
    from beets.library import Library
    lib_path = tmp_path / "beets.db"
    lib = Library(str(lib_path))
    return lib

def add_item(lib, title="Test", artist="Artist", album="Album", genre="Genre",
             year=2000, length=180, bitrate=320):
    """Add a single Item to the test library."""
    item = Item(
        path=f"/tmp/{title}.mp3",
        title=title,
        artist=artist,
        album=album,
        genre=genre,
        year=year,
        length=length,
        bitrate=bitrate
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
    """Test library with a single track."""
    add_item(library, title="Single Track", artist="Solo Artist", genre="Indie", year=2019)
    plugin = ReportPlugin()
    plugin._run_report(library, None, [])
    captured = capsys.readouterr()

    # --- Check basic statistics ---
    assert "Tracks:   1" in captured.out
    assert "Albums:   1" in captured.out
    assert "Artists:  1" in captured.out
    assert "Genres:   1" in captured.out

    # --- Wrapped-style insights ---
    assert "Top artist:   Solo Artist (1 tracks)" in captured.out
    assert "Top genre:    Indie (1 tracks)" in captured.out
    assert "Top decade:   10s (2010-2019, 1 tracks)" in captured.out
    assert "Top year:     2019 (1 tracks)" in captured.out

def test_multiple_items(capsys, library):
    """Test library with multiple tracks from different decades and genres."""
    # 1995 – 2 tracks Rock
    add_item(library, "Track1", "Artist A", "Album X", "Rock", 1995)
    add_item(library, "Track2", "Artist A", "Album X", "Rock", 1995)

    # 2002 – 1 track Pop
    add_item(library, "Track3", "Artist B", "Album Y", "Pop", 2002)

    # 2018 – 1 track Electronic
    add_item(library, "Track4", "Artist C", "Album Z", "Electronic", 2018)

    plugin = ReportPlugin()
    plugin._run_report(library, None, [])
    captured = capsys.readouterr()

    # --- Basic stats ---
    assert "Tracks:   4" in captured.out
    assert "Albums:   3" in captured.out
    assert "Artists:  3" in captured.out
    assert "Genres:   3" in captured.out

    # --- Wrapped insights ---
    assert "Top artist:   Artist A (2 tracks)" in captured.out
    assert "Top genre:    Rock (2 tracks)" in captured.out
    assert "Top decade:   90s (1990-1999, 2 tracks)" in captured.out
    assert "Top year:     1995 (2 tracks)" in captured.out

    # --- Decade distribution ---
    assert "90s (1990-1999: 2 tracks" in captured.out
    assert "00s (2000-2009: 1 tracks" in captured.out
    assert "10s (2010-2019: 1 tracks" in captured.out

def test_missing_metadata(capsys, library):
    """Test library with missing tags, length, and bitrate."""
    # Missing genre
    add_item(library, "Track1", "Artist", "Album", None, 2000, length=200, bitrate=256)
    # Missing year
    add_item(library, "Track2", "Artist", "Album", "Rock", None, length=180, bitrate=None)

    plugin = ReportPlugin()
    plugin._run_report(library, None, [])
    captured = capsys.readouterr()

    assert "Missing genre tags: 1" in captured.out
    assert "Missing year tags: 1" in captured.out

def test_various_lengths_and_bitrates(capsys, library):
    """Test track lengths and bitrate classification with different values."""
    add_item(library, "Short", "A", "X", "Pop", 2010, length=60, bitrate=128)
    add_item(library, "Long", "B", "Y", "Rock", 2015, length=3600, bitrate=1024)

    plugin = ReportPlugin()
    plugin._run_report(library, None, [])
    captured = capsys.readouterr()

    # --- Check durations ---
    assert "Total playtime:   1:01:00" in captured.out
    assert "Avg track length: 0:31:30" in captured.out

    # --- Check bitrate and quality classification ---
    assert "Avg bitrate:      576 kbps (High quality)" in captured.out
