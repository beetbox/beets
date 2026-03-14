from unittest import TestCase

from beets.util.color import color_split, uncolorize


class ColorTestCase(TestCase):
    def test_uncolorize(self):
        assert "test" == uncolorize("test")
        txt = uncolorize("\x1b[31mtest\x1b[39;49;00m")
        assert "test" == txt
        txt = uncolorize("\x1b[31mtest\x1b[39;49;00m test")
        assert "test test" == txt
        txt = uncolorize("\x1b[31mtest\x1b[39;49;00mtest")
        assert "testtest" == txt
        txt = uncolorize("test \x1b[31mtest\x1b[39;49;00m test")
        assert "test test test" == txt

    def test_color_split(self):
        exp = ("test", "")
        res = color_split("test", 5)
        assert exp == res
        exp = ("\x1b[31mtes\x1b[39;49;00m", "\x1b[31mt\x1b[39;49;00m")
        res = color_split("\x1b[31mtest\x1b[39;49;00m", 3)
        assert exp == res
