"""Test PathQuery string handling fix.

This test verifies that PathQuery correctly handles both string and bytes
patterns, which fixes the issue where path queries from command line
arguments (passed as strings) would fail to match items.
"""

import unittest

from beets.dbcore.query import PathQuery
from beets.test.helper import TestHelper


class TestPathQueryStringHandling(unittest.TestCase, TestHelper):
    """Test that PathQuery handles both string and bytes patterns correctly."""

    def setUp(self):
        """Set up test library with test items."""
        super().setUp()
        self.setup_beets()  # Initialize library
        # Add test items with various path formats
        self.add_item(path=b"/test/path/file1.mp3", title="test1")
        self.add_item(path=b"/Test/Path/With/Caps.mp3", title="test2")
        self.add_item(path=b"/path/with/[brackets]/file.mp3", title="test3")

    def tearDown(self):
        """Clean up after tests."""
        self.teardown_beets()  # Clean up library
        super().tearDown()

    def test_pathquery_accepts_string_pattern(self):
        """Test that PathQuery can be created with a string pattern."""
        # This should not raise an exception
        pq = PathQuery("path", "/test/path")
        self.assertEqual(pq.pattern, b"/test/path")
        self.assertIsInstance(pq.pattern, bytes)

    def test_pathquery_accepts_bytes_pattern(self):
        """Test that PathQuery can be created with a bytes pattern."""
        pq = PathQuery("path", b"/test/path")
        self.assertEqual(pq.pattern, b"/test/path")
        self.assertIsInstance(pq.pattern, bytes)

    def test_pathquery_string_pattern_matches_items(self):
        """Test that PathQuery with string pattern matches items correctly."""
        # Create query with string pattern (as would come from command line)
        pq = PathQuery("path", "/test/path")

        # Should match the item
        items = list(self.lib.items(pq))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "test1")

    def test_pathquery_bytes_pattern_matches_items(self):
        """Test that PathQuery with bytes pattern matches items correctly."""
        # Create query with bytes pattern
        pq = PathQuery("path", b"/test/path")

        # Should match the item
        items = list(self.lib.items(pq))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "test1")

    def test_pathquery_case_insensitive_string_pattern(self):
        """Test case-insensitive matching with string pattern."""
        # Mock case_sensitive to return False
        import beets.util

        original_case_sensitive = beets.util.case_sensitive
        try:
            beets.util.case_sensitive = lambda *_: False

            # Query with different case
            pq = PathQuery("path", "/test/path/with/caps.mp3")

            # Should match despite case difference
            items = list(self.lib.items(pq))
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].title, "test2")
        finally:
            beets.util.case_sensitive = original_case_sensitive

    def test_pathquery_with_special_chars_string_pattern(self):
        """Test PathQuery with special characters in string pattern."""
        # Query with brackets (special regex chars)
        pq = PathQuery("path", "/path/with/[brackets]")

        # Should match the item with brackets
        items = list(self.lib.items(pq))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "test3")

    def test_pathquery_directory_match_string_pattern(self):
        """Test that PathQuery matches all items in a directory with string pattern."""
        # Add another item in the same directory
        self.add_item(path=b"/test/path/file2.mp3", title="test4")

        # Query for directory with string pattern
        pq = PathQuery("path", "/test/path")

        # Should match both items in the directory
        items = list(self.lib.items(pq))
        self.assertEqual(len(items), 2)
        titles = {item.title for item in items}
        self.assertEqual(titles, {"test1", "test4"})


def suite():
    """Return the test suite for this module."""
    return unittest.TestLoader().loadTestsFromTestCase(TestPathQueryStringHandling)


if __name__ == "__main__":
    unittest.main(defaultTest="suite")