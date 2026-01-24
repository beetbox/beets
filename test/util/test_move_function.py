# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

    def test_finally_block_ignores_temp_file_cleanup_error(self):
        """Test that errors in finally block's temp file cleanup are ignored.

        Scenario:
        1. First os.replace() fails with EXDEV (cross-device)
        2. Fallback path creates temp file and copies
        3. Second os.replace() fails with PermissionError (file in use)
        4. Finally block tries to remove temp file but also fails with PermissionError
        5. The original PermissionError from step 3 should be raised as FilesystemError
        """
        # Create source and destination
        src = self.create_test_file(b"source.txt", b"source content")
        dest = os.path.join(self.temp_dir, b"dest.txt")

        # Create destination file to trigger replace=False check
        with open(syspath(dest), "wb") as f:
            f.write(b"existing content")

        # Track the sequence of operations
        operations = []

        def mock_replace(source, dest_path, *args, **kwargs):
            operations.append(f"replace: {source} -> {dest_path}")
            if len(operations) == 1:
                # First replace attempt (direct move) - cross-device error
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            else:
                # Second replace attempt (temp file to dest) - permission error
                raise OSError(errno.EACCES, "Permission denied")

        def mock_remove(path):
            operations.append(f"remove: {path}")
            # Simulate permission error when removing temp file in finally block
            if ".beets" in path:
                raise OSError(errno.EACCES, "Permission denied")
            # For non-temp files, use actual remove
            return os.remove(path)

        # Patch the system calls
        with (
            patch("os.replace", side_effect=mock_replace),
            patch("os.remove", side_effect=mock_remove),
        ):
            # This should raise FilesystemError with PermissionError
            # from the second os.replace
            with pytest.raises(FilesystemError) as cm:
                move(src, dest, replace=True)

            # Verify the error message contains info about the original error
            exception_msg = str(cm.value)
            assert "Permission denied" in exception_msg
            assert "while moving" in exception_msg

            # Verify we tried to clean up (the remove error is suppressed)
            # Check that remove was called at least once for a temp file
            temp_cleanup_attempted = any(
                ".beets" in str(op) for op in operations
            )
            assert temp_cleanup_attempted, (
                "Should have attempted temp file cleanup"
            )

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
                # Successfully remove (no exception)
                return None  # os.remove returns None

        with (
            patch("os.replace", side_effect=mock_replace),
            patch("os.remove", side_effect=mock_remove),
        ):
            # Should raise FilesystemError
            with pytest.raises(FilesystemError) as cm:
                move(src, dest, replace=True)

            # Should still get the PermissionError from os.replace
            assert "Permission denied" in str(cm.value)

            # Temp file should have been marked for removal
            assert any(".beets" in str(op) for op in operations)

            # The temp_file_removed list should have one entry
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

        # Don't create dest file so replace=True works

        operations = []
        cleanup_attempted = []

        def mock_replace(source, dest_path, *args, **kwargs):
            operations.append(f"replace: {source} -> {dest_path}")
            if len(operations) == 1:
                # First attempt fails
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            # Second attempt succeeds (no exception)

        def mock_remove(path):
            operations.append(f"remove: {path}")
            # Track if we try to remove a temp file
            if ".beets" in path:
                cleanup_attempted.append(path)
                raise AssertionError(
                    "Should not try to remove temp file after successful move!"
                )

        with (
            patch("os.replace", side_effect=mock_replace),
            patch("os.remove", side_effect=mock_remove),
        ):
            # This should succeed without errors
            move(src, dest, replace=True)

            # Verify operations sequence
            # At minimum: first replace fails, second succeeds, then remove source
            assert len(operations) >= 3

            # Should NOT have tried to cleanup temp file
            assert len(cleanup_attempted) == 0
