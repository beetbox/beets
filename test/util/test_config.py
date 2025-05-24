import unittest

from beets.util.config import sanitize_choices


class HelpersTest(unittest.TestCase):
    def test_sanitize_choices(self):
        assert sanitize_choices(["A", "Z"], ("A", "B")) == ["A"]
        assert sanitize_choices(["A", "A"], ("A")) == ["A"]
        assert sanitize_choices(["D", "*", "A"], ("A", "B", "C", "D")) == [
            "D",
            "B",
            "C",
            "A",
        ]
