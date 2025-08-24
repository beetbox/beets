#!/usr/bin/env python3
"""Simple test for PathQuery string handling fix."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from beets import config
from beets.library import Library
from beets.dbcore.query import PathQuery


def test_pathquery_string_handling():
    """Test that PathQuery correctly handles string patterns."""

    # Test 1: PathQuery accepts string pattern
    print("Test 1: PathQuery accepts string pattern... ", end="")
    try:
        pq = PathQuery("path", "/test/path")
        assert isinstance(pq.pattern, bytes), (
            f"Pattern should be bytes, got {type(pq.pattern)}"
        )
        assert pq.pattern == b"/test/path", f"Pattern incorrect: {pq.pattern}"
        print("PASSED")
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    # Test 2: PathQuery accepts bytes pattern
    print("Test 2: PathQuery accepts bytes pattern... ", end="")
    try:
        pq = PathQuery("path", b"/test/path")
        assert isinstance(pq.pattern, bytes), (
            f"Pattern should be bytes, got {type(pq.pattern)}"
        )
        assert pq.pattern == b"/test/path", f"Pattern incorrect: {pq.pattern}"
        print("PASSED")
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    # Test 3: PathQuery with actual database
    print("Test 3: PathQuery matches items in database... ", end="")
    try:
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        config["library"] = db_path
        config["directory"] = "/tmp/music"
        lib = Library(db_path)

        # Add a test item
        from beets.library import Item

        item = Item(
            path=b"/test/path/file.mp3",
            title="Test Item",
            artist="Test Artist",
            album="Test Album",
        )
        lib.add(item)

        # Test with string pattern
        pq_str = PathQuery("path", "/test/path")
        items_str = list(lib.items(pq_str))

        # Test with bytes pattern
        pq_bytes = PathQuery("path", b"/test/path")
        items_bytes = list(lib.items(pq_bytes))

        # Clean up
        os.unlink(db_path)

        assert len(items_str) == 1, (
            f"String pattern should match 1 item, got {len(items_str)}"
        )
        assert len(items_bytes) == 1, (
            f"Bytes pattern should match 1 item, got {len(items_bytes)}"
        )
        assert items_str[0].title == "Test Item", "Wrong item matched"
        print("PASSED")
    except Exception as e:
        print(f"FAILED: {e}")
        if os.path.exists(db_path):
            os.unlink(db_path)
        return False

    # Test 4: Case sensitivity handling
    print("Test 4: Case sensitivity with string pattern... ", end="")
    try:
        import beets.util

        # Test case-insensitive (mock it to return False)
        original = beets.util.case_sensitive
        beets.util.case_sensitive = lambda *_: False

        pq = PathQuery("path", "/TEST/PATH")
        assert pq.pattern == b"/test/path", (
            f"Pattern should be lowercased: {pq.pattern}"
        )

        beets.util.case_sensitive = original
        print("PASSED")
    except Exception as e:
        print(f"FAILED: {e}")
        beets.util.case_sensitive = original
        return False

    print("\nAll tests passed!")
    return True


if __name__ == "__main__":
    success = test_pathquery_string_handling()
    sys.exit(0 if success else 1)
