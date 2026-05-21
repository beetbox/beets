import os
import unittest
from unittest.mock import Mock, patch

import pytest

from beets import config, library
from beets.autotag.hooks import AlbumInfo, AlbumMatch, TrackInfo
from beets.autotag.match import distance
from beets.exceptions import UserError
from beets.test import _common
from beets.test.helper import BeetsTestCase, IOMixin
from beets.ui.commands.import_ import import_files, paths_from_logfile
from beets.ui.commands.import_.display import show_change
from beets.ui.commands.import_.session import summarize_items


class ImportTest(BeetsTestCase):
    def test_quiet_timid_disallowed(self):
        config["import"]["quiet"] = True
        config["import"]["timid"] = True
        with pytest.raises(UserError):
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


@patch("beets.ui.term_width", Mock(return_value=54))
class ShowChangeTestCase(IOMixin, BeetsTestCase):
    def _show_change(self):
        """Return an unicode string representing the changes"""
        long_name = f"a{' very' * 10} long name"
        items = [
            _common.item(track=1, title="first title"),
            _common.item(track=2, title="", path=b"/path/to/file.mp3"),
            _common.item(track=3, title="caf\xe9"),
            _common.item(track=4, title=f"title with {long_name}"),
        ]
        info = AlbumInfo(
            album="caf\xe9",
            album_id="album id",
            artist="the artist",
            artist_id="artist id",
            tracks=[
                TrackInfo(title="first title", index=1),
                TrackInfo(title="second title", index=2),
                TrackInfo(title="third title", index=3),
                TrackInfo(title="fourth title", index=4),
            ],
        )
        item_info_pairs = list(zip(items, info.tracks))
        self.config["ui"]["color"] = False
        self.config["import"]["detail"] = True
        change_dist = distance(items, info, item_info_pairs)
        change_dist._penalties = {"album": [0.1], "artist": [0.1]}
        show_change(
            f"another artist with {long_name}",
            "another album",
            AlbumMatch(change_dist, info, dict(item_info_pairs)),
        )
        return self.io.getoutput()

    def test_newline_layout(self):
        self.config["ui"]["import"]["layout"] = "newline"
        msg = self._show_change()
        assert (
            msg
            == """
  Match (90.0%):
  the artist - café
  ≠ album, artist
  None, None, None, None, None, None, None
  ≠ Artist: another artist with a very very very very
    very very very very very very long name
   -> the artist
  ≠ Album: another album -> café
     * (#1) first title (1:00)
     ≠ (#2) file.mp3 (1:00)
      -> (#2) second title (0:00)
     ≠ (#3) café (1:00) -> (#3) third title (0:00)
     ≠ (#4) title with a very very very very very very
          very very very very long name (1:00)
      -> (#4) fourth title (0:00)
"""
        )

    def test_column_layout(self):
        self.config["ui"]["import"]["layout"] = "column"
        msg = self._show_change()
        assert (
            msg
            == """
  Match (90.0%):
  the artist - café
  ≠ album, artist
  None, None, None, None, None, None, None
  ≠ Artist: another artist -> the artist              
            with a very                               
            very very very                            
            very very very                            
            very very very                            
            long name                                 
  ≠ Album: another album -> café
     * (#1) first title (1:00)
     ≠ (#2) file.mp (1:00) -> (#2) second    (0:00)
            3                      title           
     ≠ (#3) café (1:00) -> (#3) third title (0:00)
     ≠ (#4) title   (1:00) -> (#4) fourth    (0:00)
            with a very            title           
            very very very                         
            very very very                         
            very very very                         
            long name                              
"""  # noqa: W291
        )


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
