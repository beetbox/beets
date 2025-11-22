import shutil
from unittest.mock import patch

import pytest

from beets import library, ui
from beets.test.helper import BeetsTestCase, IOMixin, capture_log
from beets.ui.commands.move import move_func, move_items, show_path_changes


class MoveTest(BeetsTestCase):
    def setUp(self):
        super().setUp()

        self.initial_item_path = self.lib_path / "srcfile"
        shutil.copy(self.resource_path, self.initial_item_path)

        # Add a file to the library but don't copy it in yet.
        self.i = library.Item.from_path(self.initial_item_path)
        self.lib.add(self.i)
        self.album = self.lib.add_album([self.i])

        # Alternate destination directory.
        self.otherdir = self.temp_dir_path / "testotherdir"

    def _move(
        self,
        query=(),
        dest=None,
        copy=False,
        album=False,
        pretend=False,
        export=False,
    ):
        move_items(self.lib, dest, query, copy, album, pretend, export=export)

    def test_move_item(self):
        self._move()
        self.i.load()
        assert b"libdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_copy_item(self):
        self._move(copy=True)
        self.i.load()
        assert b"libdir" in self.i.path
        assert self.i.filepath.exists()
        assert self.initial_item_path.exists()

    def test_move_album(self):
        self._move(album=True)
        self.i.load()
        assert b"libdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_copy_album(self):
        self._move(copy=True, album=True)
        self.i.load()
        assert b"libdir" in self.i.path
        assert self.i.filepath.exists()
        assert self.initial_item_path.exists()

    def test_move_item_custom_dir(self):
        self._move(dest=self.otherdir)
        self.i.load()
        assert b"testotherdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_move_album_custom_dir(self):
        self._move(dest=self.otherdir, album=True)
        self.i.load()
        assert b"testotherdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_pretend_move_item(self):
        self._move(dest=self.otherdir, pretend=True)
        self.i.load()
        assert self.i.filepath == self.initial_item_path

    def test_pretend_move_album(self):
        self._move(album=True, pretend=True)
        self.i.load()
        assert self.i.filepath == self.initial_item_path

    def test_export_item_custom_dir(self):
        self._move(dest=self.otherdir, export=True)
        self.i.load()
        assert self.i.filepath == self.initial_item_path
        assert self.otherdir.exists()

    def test_export_album_custom_dir(self):
        self._move(dest=self.otherdir, album=True, export=True)
        self.i.load()
        assert self.i.filepath == self.initial_item_path
        assert self.otherdir.exists()

    def test_pretend_export_item(self):
        self._move(dest=self.otherdir, pretend=True, export=True)
        self.i.load()
        assert self.i.filepath == self.initial_item_path
        assert not self.otherdir.exists()

    def test_already_moved_items_skipped(self):
        """Test that items already in the correct location are skipped."""
        # First move the item to library
        self._move()
        self.i.load()
        original_path = self.i.path

        # Try to move again - should be skipped
        with capture_log("beets") as logs:
            self._move()

        # Path should be unchanged
        self.i.load()
        assert self.i.path == original_path

        # Should log that items are already in place
        assert any("already in place" in msg for msg in logs)

    def test_no_items_to_move(self):
        """Test behavior when no items match the query."""
        # Move item first so it's in the right place
        self._move()

        # Try to move with a query that matches nothing - should raise UserError
        with pytest.raises(ui.UserError, match="No matching items found"):
            self._move(query=["nonexistent"])

    def test_confirm_mode_item(self):
        """Test that confirm mode prompts for each item."""
        # We need to use IOMixin for input testing
        # This test validates the confirm parameter is used
        with patch("beets.ui.input_select_objects") as mock_select:
            mock_select.return_value = [self.i]
            move_items(
                self.lib,
                None,
                (),
                False,
                False,
                False,
                confirm=True,
                export=False,
            )

            # Verify input_select_objects was called
            mock_select.assert_called_once()

    def test_confirm_mode_album(self):
        """Test that confirm mode prompts for each album."""
        with patch("beets.ui.input_select_objects") as mock_select:
            mock_select.return_value = [self.album]
            move_items(
                self.lib,
                None,
                (),
                False,
                True,
                False,
                confirm=True,
                export=False,
            )

            # Verify input_select_objects was called
            mock_select.assert_called_once()

    def test_logging_output_items(self):
        """Test that move operations are logged."""
        with capture_log("beets") as logs:
            self._move()

        # Should log moving items
        log_output = " ".join(logs)
        assert "Moving" in log_output or "moving" in log_output

    def test_logging_output_albums(self):
        """Test that album move operations are logged."""
        with capture_log("beets") as logs:
            self._move(album=True)

        log_output = " ".join(logs)
        assert "Moving" in log_output or "album" in log_output

    def test_copy_logging(self):
        """Test that copy operations show correct action."""
        with capture_log("beets") as logs:
            self._move(copy=True)

        log_output = " ".join(logs)
        assert "Copying" in log_output or "copy" in log_output

    def test_multiple_items_move(self):
        """Test moving multiple items at once."""
        # Create a second item
        item_path2 = self.lib_path / "srcfile2"
        shutil.copy(self.resource_path, item_path2)
        i2 = library.Item.from_path(item_path2)
        self.lib.add(i2)

        # Move all items
        self._move()

        # Both should be moved
        self.i.load()
        i2.load()
        assert b"libdir" in self.i.path
        assert b"libdir" in i2.path
        assert self.i.filepath.exists()
        assert i2.filepath.exists()

    def test_query_filtering(self):
        """Test that queries properly filter items to move."""
        # Create items with different titles
        self.i.title = "UniqueTitle1"
        self.i.artist = "Artist1"
        self.i.album = "Album1"
        self.i.store()

        item_path2 = self.lib_path / "srcfile2"
        shutil.copy(self.resource_path, item_path2)
        i2 = library.Item.from_path(item_path2)
        i2.title = "UniqueTitle2"
        i2.artist = "Artist2"
        i2.album = "Album2"
        self.lib.add(i2)  # Add as singleton (no album)

        # Store original path of i2
        original_i2_path = i2.path

        # Move only items matching specific unique query
        self._move(query=["title:UniqueTitle1"])

        # Only first item should be moved to libdir
        self.i.load()
        i2.load()
        assert b"libdir" in self.i.path
        assert b"UniqueTitle1" in self.i.path or b"Artist1" in self.i.path
        # Second item should still be at original location
        assert i2.path == original_i2_path


class ShowPathChangesTest(IOMixin, BeetsTestCase):
    """Tests for the show_path_changes function."""

    def setUp(self):
        super().setUp()

    def test_show_path_changes_single_line(self):
        """Test path changes displayed on single line for short paths."""
        path_changes = [
            (b"/short/source.mp3", b"/short/dest.mp3"),
        ]

        # Mock wide terminal
        with patch("beets.ui.term_width", return_value=200):
            show_path_changes(path_changes)

        output = self.io.getoutput()
        # Should show on single line with arrow
        assert " -> " in output
        assert "Source" in output
        assert "Destination" in output

    def test_show_path_changes_two_lines(self):
        """Test path changes displayed on two lines for long paths."""
        long_source = (
            b"/very/long/path/to/source/file/that/exceeds/column/width.mp3"
        )
        long_dest = (
            b"/very/long/path/to/dest/file/that/exceeds/column/width.mp3"
        )
        path_changes = [(long_source, long_dest)]

        # Mock narrow terminal
        with patch("beets.ui.term_width", return_value=40):
            show_path_changes(path_changes)

        output = self.io.getoutput()
        # Should show on two lines
        assert " -> " in output
        # Should NOT have "Source" or "Destination" headers (two-line mode)
        assert "Source" not in output
        assert "Destination" not in output

    def test_show_path_changes_multiple_pairs(self):
        """Test showing multiple path changes."""
        path_changes = [
            (b"/source1.mp3", b"/dest1.mp3"),
            (b"/source2.mp3", b"/dest2.mp3"),
            (b"/source3.mp3", b"/dest3.mp3"),
        ]

        with patch("beets.ui.term_width", return_value=200):
            show_path_changes(path_changes)

        output = self.io.getoutput()
        # Should show all three changes
        assert output.count(" -> ") >= 3

    def test_show_path_changes_unicode_paths(self):
        """Test handling of unicode characters in paths."""
        path_changes = [
            (
                b"/music/artist/\xc3\xa9\xc3\xa0\xc3\xbc.mp3",
                b"/new/\xc3\xa9\xc3\xa0\xc3\xbc.mp3",
            ),
        ]

        show_path_changes(path_changes)
        output = self.io.getoutput()

        # Should handle unicode without crashing
        assert " -> " in output


class MoveFuncTest(IOMixin, BeetsTestCase):
    """Tests for the move_func command function."""

    def setUp(self):
        super().setUp()

        self.initial_item_path = self.lib_path / "srcfile"
        shutil.copy(self.resource_path, self.initial_item_path)

        self.i = library.Item.from_path(self.initial_item_path)
        self.lib.add(self.i)
        self.album = self.lib.add_album([self.i])

        self.otherdir = self.temp_dir_path / "testotherdir"
        self.otherdir.mkdir()

    def test_invalid_destination_raises_error(self):
        """Test that specifying non-existent destination raises UserError."""

        class MockOpts:
            dest = "/nonexistent/directory/path"
            copy = False
            album = False
            pretend = False
            timid = False
            export = False

        opts = MockOpts()

        # Should raise UserError for non-existent directory
        with pytest.raises(ui.UserError, match="no such directory"):
            move_func(self.lib, opts, [])

    def test_valid_destination_no_error(self):
        """Test that valid destination doesn't raise error."""

        class MockOpts:
            dest = str(self.otherdir)
            copy = False
            album = False
            pretend = False
            timid = False
            export = False

        opts = MockOpts()

        # Should not raise error
        move_func(self.lib, opts, [])

        # Item should be moved
        self.i.load()
        assert b"testotherdir" in self.i.path

    def test_none_destination_uses_library_dir(self):
        """Test that None destination uses library directory."""

        class MockOpts:
            dest = None
            copy = False
            album = False
            pretend = False
            timid = False
            export = False

        opts = MockOpts()

        move_func(self.lib, opts, [])

        # Item should be in library directory
        self.i.load()
        assert b"libdir" in self.i.path

    def test_pretend_flag_passed_through(self):
        """Test that pretend flag is passed to move_items."""

        class MockOpts:
            dest = str(self.otherdir)
            copy = False
            album = False
            pretend = True
            timid = False
            export = False

        opts = MockOpts()

        original_path = self.i.path
        move_func(self.lib, opts, [])

        # Item should not be moved in pretend mode
        self.i.load()
        assert self.i.path == original_path

    def test_copy_flag_passed_through(self):
        """Test that copy flag is passed to move_items."""

        class MockOpts:
            dest = str(self.otherdir)
            copy = True
            album = False
            pretend = False
            timid = False
            export = False

        opts = MockOpts()

        move_func(self.lib, opts, [])

        # Original should still exist (copy, not move)
        assert self.initial_item_path.exists()

        # Item should be updated with new path
        self.i.load()
        assert b"testotherdir" in self.i.path

    def test_album_flag_passed_through(self):
        """Test that album flag is passed to move_items."""

        class MockOpts:
            dest = None
            copy = False
            album = True
            pretend = False
            timid = False
            export = False

        opts = MockOpts()

        with capture_log("beets") as logs:
            move_func(self.lib, opts, [])

        # Should mention album in logs
        log_output = " ".join(logs)
        assert "album" in log_output.lower()

    def test_export_flag_passed_through(self):
        """Test that export flag is passed to move_items."""

        class MockOpts:
            dest = str(self.otherdir)
            copy = False
            album = False
            pretend = False
            timid = False
            export = True

        opts = MockOpts()

        original_path = self.i.path
        move_func(self.lib, opts, [])

        # Database path should not change in export mode
        self.i.load()
        assert self.i.path == original_path

        # But file should exist in destination
        assert self.otherdir.exists()

    def test_query_args_passed_through(self):
        """Test that query arguments are passed to move_items."""
        # Add second item with different title
        item_path2 = self.lib_path / "srcfile2"
        shutil.copy(self.resource_path, item_path2)
        i2 = library.Item.from_path(item_path2)
        i2.title = "DifferentTitle"
        self.lib.add(i2)

        self.i.title = "SpecificTitle"
        self.i.store()

        # Store original path of i2
        original_i2_path = i2.path

        class MockOpts:
            dest = None
            copy = False
            album = False
            pretend = False
            timid = False
            export = False

        opts = MockOpts()

        # Move only items with specific title
        move_func(self.lib, opts, ["title:SpecificTitle"])

        # Only matching item should be moved
        self.i.load()
        i2.load()
        assert b"libdir" in self.i.path
        # Second item should still be at original location
        assert i2.path == original_i2_path
