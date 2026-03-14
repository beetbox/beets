from unittest import TestCase

from beets import ui


class ColorTestCase(TestCase):
    def test_colorize(self):
        assert "test" == ui.uncolorize("test")
        txt = ui.uncolorize("\x1b[31mtest\x1b[39;49;00m")
        assert "test" == txt
        txt = ui.uncolorize("\x1b[31mtest\x1b[39;49;00m test")
        assert "test test" == txt
        txt = ui.uncolorize("\x1b[31mtest\x1b[39;49;00mtest")
        assert "testtest" == txt
        txt = ui.uncolorize("test \x1b[31mtest\x1b[39;49;00m test")
        assert "test test test" == txt

    def test_color_split(self):
        exp = ("test", "")
        res = ui.color_split("test", 5)
        assert exp == res
        exp = ("\x1b[31mtes\x1b[39;49;00m", "\x1b[31mt\x1b[39;49;00m")
        res = ui.color_split("\x1b[31mtest\x1b[39;49;00m", 3)
        assert exp == res
