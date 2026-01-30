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

"""Tests for the util.move function's finally block cleanup."""

import errno
import os
from unittest.mock import patch

import pytest

from beets.test.helper import BeetsTestCase
from beets.util import FilesystemError, bytestring_path, move, syspath


class MoveFinallyBlockTest(BeetsTestCase):
    """Test the finally block behavior in move() when cleaning up temp files."""

    def setUp(self):
        super().setUp()
        self.temp_dir = bytestring_path(self.temp_dir)

    def create_test_file(self, filename, content=b"test content"):
        """Create a test file with given content."""
        path = os.path.join(self.temp_dir, filename)
        with open(syspath(path), "wb") as f:
            f.write(content)
        return path

    def test_finally_block_raises_error_on_temp_file_cleanup_failure(self):
        """Test that errors in finally block's temp file cleanup are raised.

        Scenario:
        1. First os.replace() fails with EXDEV (cross-device)
        2. Fallback path creates temp file and copies
        3. Second os.replace() fails with PermissionError (file in use)
        4. Finally block tries to remove temp file but also fails with PermissionError
        5. The FilesystemError from finally block should be raised
        """
        src = self.create_test_file(b"source.txt", b"source content")
        dest = os.path.join(self.temp_dir, b"dest.txt")

        with open(syspath(dest), "wb") as f:
            f.write(b"existing content")

        operations = []
        temp_file_paths = []

        def mock_replace(source, dest_path, *args, **kwargs):
            operations.append(f"replace: {source} -> {dest_path}")
            if len(operations) == 1:
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            else:
                raise OSError(errno.EACCES, "Permission denied")

        def mock_remove(path):
            operations.append(f"remove: {path}")
            if ".beets" in path:
                temp_file_paths.append(path)
                raise OSError(errno.EACCES, "Permission denied")
            return os.remove(path)

        with (
            patch("os.replace", side_effect=mock_replace),
            patch("os.remove", side_effect=mock_remove),
        ):
            with pytest.raises(FilesystemError) as cm:
                move(src, dest, replace=True)

            exception_msg = str(cm.value)
            assert "Failed to remove temporary file" in exception_msg
            assert "Permission denied" in exception_msg

            assert len(temp_file_paths) == 1, (
                "Should have attempted to remove temp file"
            )
            assert "delete" in exception_msg or "remove" in exception_msg

    def test_finally_block_successful_temp_file_cleanup(self):
        """Test that finally block cleanup works when no errors occur.

        Scenario:
        1. First os.replace() fails with EXDEV (cross-device)
        2. Fallback path creates temp file and copies
        3. Second os.replace() fails with PermissionError (file in use)
        4. Finally block successfully removes temp file
        5. The original PermissionError from step 3 should be raised
        """
        src = self.create_test_file(b"source.txt", b"source content")
        dest = os.path.join(self.temp_dir, b"dest.txt")

        with open(syspath(dest), "wb") as f:
            f.write(b"existing content")

        operations = []
        temp_file_removed = []

        def mock_replace(source, dest_path, *args, **kwargs):
            operations.append(f"replace: {source} -> {dest_path}")
            if len(operations) == 1:
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            else:
                raise OSError(errno.EACCES, "Permission denied")

        def mock_remove(path):
            operations.append(f"remove: {path}")
            if ".beets" in path:
                temp_file_removed.append(path)
                return None
            return os.remove(path)

        with (
            patch("os.replace", side_effect=mock_replace),
            patch("os.remove", side_effect=mock_remove),
        ):
            with pytest.raises(FilesystemError) as cm:
                move(src, dest, replace=True)

            exception_msg = str(cm.value)
            assert "Permission denied" in exception_msg
            assert "Failed to remove temporary file" not in exception_msg

            assert len(temp_file_removed) == 1

    def test_no_temp_file_cleanup_when_move_succeeds(self):
        """Test that finally block doesn't try to cleanup
         if temp file was successfully moved.

        Scenario:
        1. First os.replace() fails with EXDEV (cross-device)
        2. Fallback path creates temp file and copies
        3. Second os.replace() succeeds (tmp_filename set to "")
        4. Original source file is removed
        5. Finally block sees tmp_filename is empty string, does nothing
        """
        src = self.create_test_file(b"source.txt", b"source content")
        dest = os.path.join(self.temp_dir, b"dest.txt")

        operations = []
        cleanup_attempted = []

        def mock_replace(source, dest_path, *args, **kwargs):
            operations.append(f"replace: {source} -> {dest_path}")
            if len(operations) == 1:
                raise OSError(errno.EXDEV, "Invalid cross-device link")

        def mock_remove(path):
            operations.append(f"remove: {path}")
            if ".beets" in path:
                cleanup_attempted.append(path)
                raise AssertionError(
                    "Should not try to remove temp file after successful move!"
                )

        with (
            patch("os.replace", side_effect=mock_replace),
            patch("os.remove", side_effect=mock_remove),
        ):
            move(src, dest, replace=True)
            assert len(operations) >= 3
            assert len(cleanup_attempted) == 0
