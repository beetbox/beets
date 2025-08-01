# This file is part of beets.
# Copyright 2025, Rebecca Turner.
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
"""Tests for the detectmissing plugin."""

from __future__ import annotations

import os
import tempfile

from beets.test.helper import PluginTestCase
from beets.util import bytestring_path, syspath


class DetectMissingPluginTest(PluginTestCase):
    plugin = "detectmissing"

    def test_detect_missing_track_file(self):
        """Test that detectmissing detects a missing track file."""
        # Add an item with a real file
        item = self.add_item_fixture()
        item_path = item.path

        # Verify the file exists
        assert os.path.exists(syspath(item_path))

        # Delete the backing file
        os.remove(syspath(item_path))

        # Run detectmissing command
        output = self.run_with_output("detectmissing")

        # Verify the missing file path is printed
        assert str(item.filepath) in output

        # Verify the item still exists in the library (no deletion without
        # --delete flag)
        items = list(self.lib.items())
        assert len(items) == 1
        assert items[0].path == item_path

    def test_detect_missing_album_art(self):
        """Test that detectmissing detects missing album art."""
        # Add an album with items
        album = self.add_album_fixture()

        # Create a temporary art file and set it as album.artpath
        handle, tmp_path = tempfile.mkstemp(suffix=".jpg")
        os.close(handle)
        album.artpath = bytestring_path(tmp_path)
        album.store()

        # Verify the art file exists
        assert os.path.exists(tmp_path)

        # Delete the art file
        os.remove(tmp_path)

        # Run detectmissing command
        output = self.run_with_output("detectmissing")

        # Verify the missing art path is printed
        assert tmp_path in output

        # Verify the album still has the artpath reference (no deletion without
        # --delete flag)
        albums = list(self.lib.albums())
        assert len(albums) == 1
        assert albums[0].artpath == bytestring_path(tmp_path)

    def test_delete_missing_track_file(self):
        """Test that detectmissing --delete removes items with missing files."""
        # Add an item with a real file
        item = self.add_item_fixture()
        item_path = item.path
        item_dir = os.path.dirname(syspath(item_path))

        # Verify the file exists
        assert os.path.exists(syspath(item_path))

        # Delete the backing file
        os.remove(syspath(item_path))

        # Run detectmissing --delete
        output = self.run_with_output("detectmissing", "--delete")

        # Verify the missing file path is printed
        assert str(item.filepath) in output

        # Verify the item is removed from the library
        items = list(self.lib.items())
        assert len(items) == 0

        # Verify empty parent directories are pruned
        # The directory should be removed if it's now empty
        assert not os.path.exists(item_dir)

    def test_delete_missing_album_art(self):
        """Test that detectmissing --delete clears artpath for missing album art."""
        # Add an album with items
        album = self.add_album_fixture()

        # Create a temporary art file and assign it
        handle, tmp_path = tempfile.mkstemp(suffix=".jpg")
        os.close(handle)
        album.artpath = bytestring_path(tmp_path)
        album.store()

        # Verify the art file exists
        assert os.path.exists(tmp_path)

        # Delete the art file
        os.remove(tmp_path)

        # Run detectmissing --delete
        output = self.run_with_output("detectmissing", "--delete")

        # Verify the missing art path is printed
        assert tmp_path in output

        # Verify the album's artpath is set to None
        albums = list(self.lib.albums())
        assert len(albums) == 1
        assert albums[0].artpath is None

        # Verify the album still exists in library (only art reference removed)
        assert len(list(self.lib.albums())) == 1

    def test_no_missing_files(self):
        """Test that detectmissing produces no output when all files are present."""
        # Add items and albums with all files present
        item = self.add_item_fixture()
        album = self.add_album_fixture()

        # Verify files exist
        assert os.path.exists(syspath(item.path))
        for album_item in album.items():
            assert os.path.exists(syspath(album_item.path))

        # Run detectmissing
        output = self.run_with_output("detectmissing")

        # Verify no output is produced
        assert output.strip() == ""

        # Verify all items remain in library
        assert len(list(self.lib.items())) == 2  # 1 from item, 1 from album
