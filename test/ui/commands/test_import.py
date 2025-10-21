import os
import re
import unittest
from unittest.mock import Mock, patch

import pytest

from beets import autotag, config, library, ui
from beets.autotag.match import distance
from beets.test import _common
from beets.test.helper import BeetsTestCase, IOMixin
from beets.ui.commands.import_ import import_files, paths_from_logfile
from beets.ui.commands.import_.display import show_change
from beets.ui.commands.import_.session import summarize_items


class ImportTest(BeetsTestCase):
    def test_quiet_timid_disallowed(self):
        config["import"]["quiet"] = True
        config["import"]["timid"] = True
        with pytest.raises(ui.UserError):
            import_files(None, [], None)

    def test_parse_paths_from_logfile(self):
        if os.path.__name__ == "ntpath":
            logfile_content = (
                "import started Wed Jun 15 23:08:26 2022\n"
                "asis C:\\music\\Beatles, The\\The Beatles; C:\\music\\Beatles, The\\The Beatles\\CD 01; C:\\music\\Beatles, The\\The Beatles\\CD 02\n"  # noqa: E501
                "duplicate-replace C:\\music\\Bill Evans\\Trio '65\n"
                "skip C:\\music\\Michael Jackson\\Bad\n"
                "skip C:\\music\\Soulwax\\Any Minute Now\n"
            )
            expected_paths = [
                "C:\\music\\Beatles, The\\The Beatles",
                "C:\\music\\Michael Jackson\\Bad",
                "C:\\music\\Soulwax\\Any Minute Now",
            ]
        else:
            logfile_content = (
                "import started Wed Jun 15 23:08:26 2022\n"
                "asis /music/Beatles, The/The Beatles; /music/Beatles, The/The Beatles/CD 01; /music/Beatles, The/The Beatles/CD 02\n"  # noqa: E501
                "duplicate-replace /music/Bill Evans/Trio '65\n"
                "skip /music/Michael Jackson/Bad\n"
                "skip /music/Soulwax/Any Minute Now\n"
            )
            expected_paths = [
                "/music/Beatles, The/The Beatles",
                "/music/Michael Jackson/Bad",
                "/music/Soulwax/Any Minute Now",
            ]

        logfile = os.path.join(self.temp_dir, b"logfile.log")
        with open(logfile, mode="w") as fp:
            fp.write(logfile_content)
        actual_paths = list(paths_from_logfile(logfile))
        assert actual_paths == expected_paths


class ShowChangeTest(IOMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()

        self.items = [_common.item()]
        self.items[0].track = 1
        self.items[0].path = b"/path/to/file.mp3"
        self.info = autotag.AlbumInfo(
            album="the album",
            album_id="album id",
            artist="the artist",
            artist_id="artist id",
            tracks=[
                autotag.TrackInfo(
                    title="the title", track_id="track id", index=1
                )
            ],
        )

    def _show_change(
        self,
        items=None,
        info=None,
        color=False,
        cur_artist="the artist",
        cur_album="the album",
        dist=0.1,
    ):
        """Return an unicode string representing the changes"""
        items = items or self.items
        info = info or self.info
        mapping = dict(zip(items, info.tracks))
        config["ui"]["color"] = color
        config["import"]["detail"] = True
        change_dist = distance(items, info, mapping)
        change_dist._penalties = {"album": [dist], "artist": [dist]}
        show_change(
            cur_artist,
            cur_album,
            autotag.AlbumMatch(change_dist, info, mapping, set(), set()),
        )
        return self.io.getoutput().lower()

    def test_null_change(self):
        msg = self._show_change()
        assert "match (90.0%)" in msg
        assert "album, artist" in msg

    def test_album_data_change(self):
        msg = self._show_change(
            cur_artist="another artist", cur_album="another album"
        )
        assert "another artist -> the artist" in msg
        assert "another album -> the album" in msg

    def test_item_data_change(self):
        self.items[0].title = "different"
        msg = self._show_change()
        assert "different" in msg
        assert "the title" in msg

    def test_item_data_change_with_unicode(self):
        self.items[0].title = "caf\xe9"
        msg = self._show_change()
        assert "caf\xe9" in msg
        assert "the title" in msg

    def test_album_data_change_with_unicode(self):
        msg = self._show_change(cur_artist="caf\xe9", cur_album="another album")
        assert "caf\xe9" in msg
        assert "the artist" in msg

    def test_item_data_change_title_missing(self):
        self.items[0].title = ""
        msg = re.sub(r"  +", " ", self._show_change())
        assert "file.mp3" in msg
        assert "the title" in msg

    def test_item_data_change_title_missing_with_unicode_filename(self):
        self.items[0].title = ""
        self.items[0].path = "/path/to/caf\xe9.mp3".encode()
        msg = re.sub(r"  +", " ", self._show_change())
        assert "caf\xe9.mp3" in msg or "caf.mp3" in msg

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

    def test_split_into_lines(self):
        # Test uncolored text
        txt = ui.split_into_lines("test test test", [5, 5, 5])
        assert txt == ["test", "test", "test"]
        # Test multiple colored texts
        colored_text = "\x1b[31mtest \x1b[39;49;00m" * 3
        split_txt = [
            "\x1b[31mtest\x1b[39;49;00m",
            "\x1b[31mtest\x1b[39;49;00m",
            "\x1b[31mtest\x1b[39;49;00m",
        ]
        txt = ui.split_into_lines(colored_text, [5, 5, 5])
        assert txt == split_txt
        # Test single color, multi space text
        colored_text = "\x1b[31m test test test \x1b[39;49;00m"
        txt = ui.split_into_lines(colored_text, [5, 5, 5])
        assert txt == split_txt
        # Test single color, different spacing
        colored_text = "\x1b[31mtest\x1b[39;49;00mtest test test"
        # ToDo: fix color_len to handle mid-text color escapes, and thus
        # split colored texts over newlines (potentially with dashes?)
        split_txt = ["\x1b[31mtest\x1b[39;49;00mt", "est", "test", "test"]
        txt = ui.split_into_lines(colored_text, [5, 5, 5])
        assert txt == split_txt

    def test_album_data_change_wrap_newline(self):
        # Patch ui.term_width to force wrapping
        with patch("beets.ui.term_width", return_value=30):
            # Test newline layout
            config["ui"]["import"]["layout"] = "newline"
            long_name = f"another artist with a{' very' * 10} long name"
            msg = self._show_change(
                cur_artist=long_name, cur_album="another album"
            )
            assert "artist: another artist" in msg
            assert "  -> the artist" in msg
            assert "another album -> the album" not in msg

    def test_item_data_change_wrap_column(self):
        # Patch ui.term_width to force wrapping
        with patch("beets.ui.term_width", return_value=54):
            # Test Column layout
            config["ui"]["import"]["layout"] = "column"
            long_title = f"a track with a{' very' * 10} long name"
            self.items[0].title = long_title
            msg = self._show_change()
            assert "(#1) a track (1:00) -> (#1) the title (0:00)" in msg

    def test_item_data_change_wrap_newline(self):
        # Patch ui.term_width to force wrapping
        with patch("beets.ui.term_width", return_value=30):
            config["ui"]["import"]["layout"] = "newline"
            long_title = f"a track with a{' very' * 10} long name"
            self.items[0].title = long_title
            msg = self._show_change()
            assert "(#1) a track with" in msg
            assert "     -> (#1) the title (0:00)" in msg


@patch("beets.library.Item.try_filesize", Mock(return_value=987))
class SummarizeItemsTest(unittest.TestCase):
    def setUp(self):
        super().setUp()
        item = library.Item()
        item.bitrate = 4321
        item.length = 10 * 60 + 54
        item.format = "F"
        self.item = item

    def test_summarize_item(self):
        summary = summarize_items([], True)
        assert summary == ""

        summary = summarize_items([self.item], True)
        assert summary == "F, 4kbps, 10:54, 987.0 B"

    def test_summarize_items(self):
        summary = summarize_items([], False)
        assert summary == "0 items"

        summary = summarize_items([self.item], False)
        assert summary == "1 items, F, 4kbps, 10:54, 987.0 B"

        # make a copy of self.item
        i2 = self.item.copy()

        summary = summarize_items([self.item, i2], False)
        assert summary == "2 items, F, 4kbps, 21:48, 1.9 KiB"

        i2.format = "G"
        summary = summarize_items([self.item, i2], False)
        assert summary == "2 items, F 1, G 1, 4kbps, 21:48, 1.9 KiB"

        summary = summarize_items([self.item, i2, i2], False)
        assert summary == "3 items, G 2, F 1, 4kbps, 32:42, 2.9 KiB"
