"""Tests for the 'stats' command."""

import os
from unittest.mock import patch

from beets.test.helper import BeetsTestCase, IOMixin
from beets.ui.commands.stats import show_stats, stats_func


class StatsTest(IOMixin, BeetsTestCase):
    """Tests for the stats command."""

    def setUp(self):
        super().setUp()

    def test_stats_basic(self):
        """Test basic stats output with single item in an album."""
        # Create an album with one item
        album = self.add_album_fixture()
        item = album.items().get()
        item.length = 180.0  # 3 minutes
        item.bitrate = 320000  # 320 kbps
        item.store()

        show_stats(self.lib, [], exact=False)

        output = self.io.getoutput()
        assert "Tracks: 1" in output
        assert "Artists: 1" in output
        assert "Albums: 1" in output
        assert "Album artists: 1" in output
        assert "Total time:" in output
        assert "Approximate total size:" in output

    def test_stats_multiple_items(self):
        """Test stats with multiple items across different albums."""
        # Create first album with one item
        album1 = self.add_album_fixture()
        item1 = album1.items().get()
        item1.artist = "Artist1"
        item1.albumartist = "AlbumArtist1"
        item1.length = 120.0
        item1.bitrate = 320000
        item1.store()

        # Create second album with one item
        album2 = self.add_album_fixture()
        item2 = album2.items().get()
        item2.artist = "Artist2"
        item2.albumartist = "AlbumArtist2"
        item2.length = 180.0
        item2.bitrate = 256000
        item2.store()

        # Add another item to first album
        item3 = self.add_item_fixture()
        item3.album_id = album1.id
        item3.artist = "Artist1"  # Same artist as item1
        item3.albumartist = "AlbumArtist1"  # Same album artist as item1
        item3.length = 150.0
        item3.bitrate = 320000
        item3.store()

        show_stats(self.lib, [], exact=False)

        output = self.io.getoutput()
        assert "Tracks: 3" in output
        assert "Artists: 2" in output  # Artist1 and Artist2
        assert "Albums: 2" in output  # album1 and album2
        assert "Album artists: 2" in output  # AlbumArtist1 and AlbumArtist2

    def test_stats_exact_mode(self):
        """Test stats with exact flag for precise size and time."""
        item = self.add_item_fixture(
            title="Track",
            artist="Artist",
            album="Album",
            albumartist="AlbumArtist",
            length=180.5,
            bitrate=320000,
        )

        show_stats(self.lib, [], exact=True)

        output = self.io.getoutput()
        assert "Tracks: 1" in output
        assert "Total size:" in output
        assert "bytes)" in output  # Exact mode shows bytes
        assert "seconds)" in output  # Exact mode shows seconds
        assert "Approximate" not in output  # Should not say "Approximate"

    def test_stats_exact_mode_file_size(self):
        """Test that exact mode uses actual file size."""
        item = self.add_item_fixture(
            title="Track",
            artist="Artist",
            album="Album",
            albumartist="AlbumArtist",
            length=180.0,
            bitrate=320000,
        )

        # Mock os.path.getsize to return a known size
        with patch("os.path.getsize") as mock_getsize:
            mock_getsize.return_value = 1234567

            show_stats(self.lib, [], exact=True)

            output = self.io.getoutput()
            assert "1234567 bytes" in output
            assert mock_getsize.called

    def test_stats_exact_mode_file_not_found(self):
        """Test exact mode when file doesn't exist (OSError)."""
        item = self.add_item_fixture(
            title="Track",
            artist="Artist",
            album="Album",
            albumartist="AlbumArtist",
            length=180.0,
            bitrate=320000,
        )

        # Mock os.path.getsize to raise OSError
        with patch("os.path.getsize") as mock_getsize:
            mock_getsize.side_effect = OSError("File not found")

            show_stats(self.lib, [], exact=True)

            output = self.io.getoutput()
            # Should still show stats, but size will be 0 for missing file
            assert "Tracks: 1" in output
            assert mock_getsize.called

    def test_stats_with_query(self):
        """Test stats with query filter."""
        self.add_item_fixture(
            title="Rock1",
            artist="RockArtist",
            album="RockAlbum",
            albumartist="RockAlbumArtist",
            length=200.0,
            bitrate=320000,
        )
        self.add_item_fixture(
            title="Jazz1",
            artist="JazzArtist",
            album="JazzAlbum",
            albumartist="JazzAlbumArtist",
            length=180.0,
            bitrate=256000,
        )

        # Query for only Rock items
        show_stats(self.lib, ["artist:RockArtist"], exact=False)

        output = self.io.getoutput()
        assert "Tracks: 1" in output
        assert "Artists: 1" in output

    def test_stats_singleton_items(self):
        """Test stats with singleton items (no album_id)."""
        # Create item without album_id (singleton)
        item = self.add_item_fixture(
            title="SingletonTrack",
            artist="Artist",
            albumartist="AlbumArtist",
            length=150.0,
            bitrate=192000,
        )
        # Remove album association to make it a true singleton
        item.album_id = None
        item.store()

        show_stats(self.lib, [], exact=False)

        output = self.io.getoutput()
        assert "Tracks: 1" in output
        assert "Albums: 0" in output  # No album since it's a singleton

    def test_stats_empty_library(self):
        """Test stats with empty library."""
        show_stats(self.lib, [], exact=False)

        output = self.io.getoutput()
        assert "Tracks: 0" in output
        assert "Artists: 0" in output
        assert "Albums: 0" in output

    def test_stats_no_matching_query(self):
        """Test stats with query that matches no items."""
        self.add_item_fixture(
            title="Track",
            artist="Artist",
            album="Album",
            albumartist="AlbumArtist",
            length=180.0,
            bitrate=320000,
        )

        show_stats(self.lib, ["artist:NonExistent"], exact=False)

        output = self.io.getoutput()
        assert "Tracks: 0" in output


class StatsFuncTest(IOMixin, BeetsTestCase):
    """Tests for the stats_func command function."""

    def setUp(self):
        super().setUp()
        self.item = self.add_item_fixture(
            title="Track",
            artist="Artist",
            album="Album",
            albumartist="AlbumArtist",
            length=180.0,
            bitrate=320000,
        )

    def test_stats_func_without_exact(self):
        """Test stats_func respects exact flag when False."""

        class MockOpts:
            exact = False

        opts = MockOpts()
        stats_func(self.lib, opts, [])

        output = self.io.getoutput()
        assert "Tracks: 1" in output
        assert "Approximate total size:" in output

    def test_stats_func_with_exact(self):
        """Test stats_func respects exact flag when True."""

        class MockOpts:
            exact = True

        opts = MockOpts()
        stats_func(self.lib, opts, [])

        output = self.io.getoutput()
        assert "Tracks: 1" in output
        assert "bytes)" in output

    def test_stats_func_with_query(self):
        """Test stats_func passes query arguments."""
        self.add_item_fixture(
            title="Track2",
            artist="Artist2",
            album="Album2",
            albumartist="AlbumArtist2",
            length=120.0,
            bitrate=256000,
        )

        class MockOpts:
            exact = False

        opts = MockOpts()
        stats_func(self.lib, opts, ["artist:Artist2"])

        output = self.io.getoutput()
        assert "Tracks: 1" in output  # Only one track matches query
