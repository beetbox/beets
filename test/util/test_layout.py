from unittest import TestCase

from beets.util.color import uncolorize
from beets.util.layout import split_into_lines


class LayoutTestCase(TestCase):
    def test_split_into_lines(self):
        # Test uncolored text
        txt = split_into_lines("test test test", 5, 5)
        assert txt == ["test", "test", "test"]
        # Test multiple colored texts
        colored_text = "\x1b[31mtest \x1b[39;49;00m" * 3
        split_txt = [
            "\x1b[31mtest\x1b[39;49;00m",
            "\x1b[31mtest\x1b[39;49;00m",
            "\x1b[31mtest\x1b[39;49;00m",
        ]
        txt = split_into_lines(colored_text, 5, 5)
        assert txt == split_txt
        # Test single color, multi space text
        colored_text = "\x1b[31m test test test \x1b[39;49;00m"
        txt = split_into_lines(colored_text, 5, 5)
        assert txt == split_txt
        # Test single color, different spacing
        colored_text = "\x1b[31mtest\x1b[39;49;00mtest test test"
        # ToDo: fix color_len to handle mid-text color escapes, and thus
        # split colored texts over newlines (potentially with dashes?)
        split_txt = ["\x1b[31mtest\x1b[39;49;00mt", "est", "test", "test"]
        txt = split_into_lines(colored_text, 5, 5)
        assert txt == split_txt

    def test_split_into_lines_two_spans_in_one_word(self):
        # A single word containing two separately-colored, non-adjacent
        # spans (e.g. two highlighted typo fixes within one word) must stay
        # one word, not get split at the second colored span.
        red, reset = "\x1b[31m", "\x1b[39;49;00m"
        colored_text = f"extra{red}A{reset}ordin{red}B{reset}ary"
        txt = split_into_lines(colored_text, 100, 100)
        assert len(txt) == 1
        assert " " not in uncolorize(txt[0])
        assert uncolorize(txt[0]) == "extraAordinBary"
