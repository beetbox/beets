import os
from unittest.mock import patch

from beets import library
from beets.test.helper import BeetsTestCase, capture_log
from beets.ui.commands.write import write_items


class WriteTest(BeetsTestCase):
    def write_cmd(self, *args):
        return self.run_with_output("write", *args)

    def test_update_mtime(self):
        item = self.add_item_fixture()
        item["title"] = "a new title"
        item.store()

        item = self.lib.items().get()
        assert item.mtime == 0

        self.write_cmd()
        item = self.lib.items().get()
        assert item.mtime == item.current_mtime()

    def test_non_metadata_field_unchanged(self):
        """Changing a non-"tag" field like `bitrate` and writing should
        have no effect.
        """
        # An item that starts out "clean".
        item = self.add_item_fixture()
        item.read()

        # ... but with a mismatched bitrate.
        item.bitrate = 123
        item.store()

        output = self.write_cmd()

        assert output == ""

    def test_write_metadata_field(self):
        item = self.add_item_fixture()
        item.read()
        old_title = item.title

        item.title = "new title"
        item.store()

        output = self.write_cmd()

        assert f"{old_title} -> new title" in output

    def test_write_missing_file(self):
        """Test that write command logs info when file is missing."""
        item = self.add_item_fixture()
        item_path = item.path

        # Delete the file to simulate missing file
        os.remove(item_path)

        with capture_log("beets") as logs:
            write_items(self.lib, [], pretend=False, force=False)

        log_output = " ".join(logs)
        assert "missing file" in log_output

    def test_write_read_error(self):
        """Test that write command logs error when file can't be read."""
        item = self.add_item_fixture()
        item.title = "modified title"
        item.store()

        # Mock Item.from_path to raise ReadError
        with patch("beets.library.Item.from_path") as mock_from_path:
            mock_from_path.side_effect = library.ReadError(
                item.path, "corrupted file"
            )

            with capture_log("beets") as logs:
                write_items(self.lib, [], pretend=False, force=False)

            log_output = " ".join(logs)
            assert "error reading" in log_output

    def test_write_pretend_mode(self):
        """Test that pretend mode shows changes but doesn't write."""
        item = self.add_item_fixture()
        item.read()
        item.title = "new title"
        item.store()

        # Run with pretend mode
        output = self.write_cmd("--pretend")

        # Should show the change
        assert "new title" in output

        # Verify the file wasn't actually written by reading it back
        clean_item = library.Item.from_path(item.path)
        assert clean_item.title != "new title"

    def test_write_force_mode(self):
        """Test that force mode writes even when tags match the library."""
        # Create an item and write its tags once so the file tags match the library
        item = self.add_item_fixture()
        self.write_cmd()  # Initial write to sync tags without forcing

        # Capture the file's mtime after the initial write
        import time
        time.sleep(0.01)  # Ensure mtime difference is detectable
        original_mtime = os.path.getmtime(item.path)

        # Run write with --force; even though tags are unchanged, this should
        # trigger a write and thus update the file's mtime
        self.write_cmd("--force")
        new_mtime = os.path.getmtime(item.path)

        # Verify that a write occurred by asserting the mtime changed
        assert new_mtime > original_mtime


class WriteItemsTest(BeetsTestCase):
    """Tests for the write_items function."""

    def test_write_items_with_query(self):
        """Test write_items with query filter."""
        item1 = self.add_item_fixture(title="Item1", artist="Artist1")
        item2 = self.add_item_fixture(title="Item2", artist="Artist2")

        # Modify both items
        item1.title = "Modified1"
        item1.store()
        item2.title = "Modified2"
        item2.store()

        # Write only items matching query
        write_items(self.lib, ["artist:Artist1"], pretend=False, force=False)

        # Verify only item1 was written
        clean_item1 = library.Item.from_path(item1.path)
        clean_item2 = library.Item.from_path(item2.path)

        assert clean_item1.title == "Modified1"
        assert clean_item2.title != "Modified2"  # Should not be written

    def test_write_items_no_changes(self):
        """Test write_items when there are no changes."""
        item = self.add_item_fixture()
        item.read()  # Make item match file

        # Write with no changes
        write_items(self.lib, [], pretend=False, force=False)

        # Should complete without errors (nothing to write)
        item.load()
        assert item.mtime >= 0
