"""Test PathQuery string handling fix.

This test verifies that PathQuery correctly handles both string and bytes
patterns, which fixes the issue where path queries from command line
arguments (passed as strings) would fail to match items.
"""

import os
import sys
import tempfile
import unittest

from beets.dbcore.query import PathQuery
from beets.test.helper import TestHelper
from beets.util import bytestring_path


class TestPathQueryStringHandling(unittest.TestCase, TestHelper):
    """Test that PathQuery handles both string and bytes patterns correctly."""

    def setUp(self):
        """Set up test library with test items."""
        super().setUp()
        self.setup_beets()  # Initialize library

    def tearDown(self):
        """Clean up after tests."""
        self.teardown_beets()  # Clean up library
        super().tearDown()

    def test_pathquery_accepts_string_pattern(self):
        """Test that PathQuery can be created with a string pattern."""
        # This should not raise an exception
        pq = PathQuery("path", "/test/path")
        # PathQuery normalizes paths, so we just check it's bytes
        assert isinstance(pq.pattern, bytes)

    def test_pathquery_accepts_bytes_pattern(self):
        """Test that PathQuery can be created with a bytes pattern."""
        pq = PathQuery("path", b"/test/path")
        # PathQuery normalizes paths, so we just check it's bytes
        assert isinstance(pq.pattern, bytes)

    def test_pathquery_string_pattern_matches_items(self):
        """Test that PathQuery with string pattern matches items correctly."""
        # Create a temporary file to ensure path exists
        # Convert temp_dir from bytes to string for tempfile
        temp_dir_str = self.temp_dir.decode("utf-8")
        with tempfile.NamedTemporaryFile(
            suffix=".mp3", dir=temp_dir_str, delete=False
        ) as f:
            temp_path = f.name

        # Add item with the actual temp path
        self.add_item(path=bytestring_path(temp_path), title="test_string")

        # Create query with string pattern for the directory
        temp_dir = os.path.dirname(temp_path)
        pq = PathQuery("path", temp_dir)

        # Should match the item
        items = list(self.lib.items(pq))
        assert len(items) >= 1
        assert any(item.title == "test_string" for item in items)

    def test_pathquery_bytes_pattern_matches_items(self):
        """Test that PathQuery with bytes pattern matches items correctly."""
        # Create a temporary file to ensure path exists
        # Convert temp_dir from bytes to string for tempfile
        temp_dir_str = self.temp_dir.decode("utf-8")
        with tempfile.NamedTemporaryFile(
            suffix=".mp3", dir=temp_dir_str, delete=False
        ) as f:
            temp_path = f.name

        # Add item with the actual temp path
        self.add_item(path=bytestring_path(temp_path), title="test_bytes")

        # Create query with bytes pattern for the directory
        temp_dir = os.path.dirname(temp_path)
        pq = PathQuery("path", bytestring_path(temp_dir))

        # Should match the item
        items = list(self.lib.items(pq))
        assert len(items) >= 1
        assert any(item.title == "test_bytes" for item in items)

    @unittest.skipIf(sys.platform == "win32", "Case sensitivity test for Unix")
    def test_pathquery_case_insensitive_string_pattern(self):
        """Test case-insensitive matching with string pattern."""
        # Create paths with different cases
        test_dir = os.path.join(self.temp_dir, b"TestDir")
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, b"file.mp3")

        self.add_item(path=test_file, title="test_case")

        # Mock case_sensitive to return False
        import beets.util

        original_case_sensitive = beets.util.case_sensitive
        try:
            beets.util.case_sensitive = lambda *_: False

            # Query with different case - use lowercase
            # Convert temp_dir to string and join with string
            temp_dir_str = self.temp_dir.decode("utf-8")
            query_path = os.path.join(temp_dir_str, "testdir")
            pq = PathQuery("path", query_path)

            # Should match despite case difference
            items = list(self.lib.items(pq))
            assert any(item.title == "test_case" for item in items)
        finally:
            beets.util.case_sensitive = original_case_sensitive

    def test_pathquery_with_special_chars_string_pattern(self):
        """Test PathQuery with special characters in string pattern."""
        # Create a directory with brackets (special regex chars)
        special_dir = os.path.join(self.temp_dir, b"[special]")
        os.makedirs(special_dir, exist_ok=True)
        special_file = os.path.join(special_dir, b"file.mp3")

        self.add_item(path=special_file, title="test_special")

        # Query with brackets
        # Convert temp_dir to string and join with string
        temp_dir_str = self.temp_dir.decode("utf-8")
        query_path = os.path.join(temp_dir_str, "[special]")
        pq = PathQuery("path", query_path)

        # Should match the item with brackets
        items = list(self.lib.items(pq))
        assert any(item.title == "test_special" for item in items)

    def test_pathquery_directory_match_string_pattern(self):
        """Test that PathQuery matches all items in a directory with string pattern."""
        # Create a test directory
        test_dir = os.path.join(self.temp_dir, b"test_multi")
        os.makedirs(test_dir, exist_ok=True)

        # Add multiple items in the same directory
        file1 = os.path.join(test_dir, b"file1.mp3")
        file2 = os.path.join(test_dir, b"file2.mp3")
        self.add_item(path=file1, title="test_multi1")
        self.add_item(path=file2, title="test_multi2")

        # Query for directory with string pattern
        # Convert temp_dir to string and join with string
        temp_dir_str = self.temp_dir.decode("utf-8")
        query_path = os.path.join(temp_dir_str, "test_multi")
        pq = PathQuery("path", query_path)

        # Should match both items in the directory
        items = list(self.lib.items(pq))
        titles = {item.title for item in items}
        assert "test_multi1" in titles
        assert "test_multi2" in titles


def suite():
    """Return the test suite for this module."""
    return unittest.TestLoader().loadTestsFromTestCase(
        TestPathQueryStringHandling
    )


if __name__ == "__main__":
    unittest.main(defaultTest="suite")
