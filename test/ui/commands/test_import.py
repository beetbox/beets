import json
import ntpath
import os
import posixpath
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from beets import config, library, logging
from beets.autotag import AlbumInfo, AlbumMatch, Source, TrackInfo, distance
from beets.exceptions import UserError
from beets.test import _common
from beets.test.helper import BeetsTestCase, IOMixin
from beets.ui.commands.import_ import paths_from_logfile
from beets.ui.commands.import_.display import show_change
from beets.ui.commands.import_.session import summarize_items


@pytest.mark.parametrize("status", ["asis", "skip", "duplicate-skip"])
@pytest.mark.parametrize("path_module", [posixpath, ntpath])
@pytest.mark.parametrize("multidisc", [False, True])
@pytest.mark.parametrize(
    "album", ["Artist; The Band", 'Album; "Deluxe" café', "Album\nDeluxe"]
)
def test_log_paths_roundtrip(
    tmp_path, module_helper, monkeypatch, status, path_module, multidisc, album
):
    root = path_module.join("F:/Music", album)
    paths = (
        [path_module.join(root, "CD 01"), path_module.join(root, "CD 02")]
        if multidisc
        else [root]
    )
    stream = StringIO()
    session = _common.import_session(
        module_helper.lib, loghandler=logging.StreamHandler(stream)
    )
    session.tag_log(status, [os.fsencode(path) for path in paths])
    logfile = tmp_path / "import.log"
    logfile.write_text(stream.getvalue(), encoding="utf-8")
    monkeypatch.setattr(
        "beets.ui.commands.import_.os", SimpleNamespace(path=path_module)
    )

    assert list(paths_from_logfile(logfile)) == [path_module.commonpath(paths)]


@pytest.mark.parametrize(
    "paths", [[b"/music/Album"], [b"/music/A;B", b"/music/A;B/CD"]]
)
def test_log_paths_preserve_legacy_output(module_helper, paths):
    stream = StringIO()
    session = _common.import_session(
        module_helper.lib, loghandler=logging.StreamHandler(stream)
    )
    session.tag_log("skip", paths)

    assert stream.getvalue() == f"skip {'; '.join(map(os.fsdecode, paths))}\n"


@pytest.mark.parametrize("path", ["café", b"path", Path("path")])
def test_log_paths_single_path_argument(module_helper, path):
    stream = StringIO()
    session = _common.import_session(
        module_helper.lib, loghandler=logging.StreamHandler(stream)
    )
    session.tag_log("skip", path)

    assert stream.getvalue() == f"skip {os.fsdecode(path)}\n"


def test_log_paths_mixed_formats(tmp_path):
    logfile = tmp_path / "import.log"
    logfile.write_text(
        'skip ["literal path"]\n'
        'skip-json ["/music/Artist; Band"]\n'
        "asis /music/Album; /music/Album/CD 01\n",
        encoding="utf-8",
    )

    assert list(paths_from_logfile(logfile)) == [
        '["literal path"]',
        os.path.normpath("/music/Artist; Band"),
        os.path.normpath("/music/Album"),
    ]


def test_log_paths_do_not_guess_ambiguous_legacy_paths(tmp_path):
    logfile = tmp_path / "import.log"
    logfile.write_text("skip /music/Artist; Band/Album\n", encoding="utf-8")

    with pytest.raises(ValueError, match="absolute and relative"):
        list(paths_from_logfile(logfile))


@pytest.mark.parametrize(
    "status", ["import", "duplicate-keep", "duplicate-replace"]
)
def test_log_paths_ignore_structured_information(tmp_path, status):
    logfile = tmp_path / "import.log"
    logfile.write_text(
        f'{status}-json ["/music/Artist; Band"]\n', encoding="utf-8"
    )

    assert list(paths_from_logfile(logfile)) == []


@pytest.mark.parametrize(
    "payload", ["[", '"path"', "{}", "[]", "[1]", '[""]', "[null]"]
)
def test_log_paths_reject_invalid_structured_records(tmp_path, payload):
    logfile = tmp_path / "import.log"
    logfile.write_text(
        f"import started now\nskip-json {payload}\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="line 2 is invalid"):
        list(paths_from_logfile(logfile))


def test_log_paths_structured_escaping(tmp_path):
    path = '/music/Artist; Band/Album "Deluxe"\\ café'
    logfile = tmp_path / "import.log"
    logfile.write_text(f"skip-json {json.dumps([path])}\n", encoding="utf-8")

    assert list(paths_from_logfile(logfile)) == [os.path.commonpath([path])]


class ImportTest(BeetsTestCase):
    def test_quiet_timid_disallowed(self):
        config["import"]["quiet"] = True
        config["import"]["timid"] = True
        with pytest.raises(UserError):
            self.run_command("import")

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

        logfile = self.temp_path / "logfile.log"
        logfile.write_text(logfile_content)
        actual_paths = list(paths_from_logfile(logfile))
        assert actual_paths == expected_paths


@patch("beets.ui.term_width", Mock(return_value=54))
class ShowChangeTestCase(IOMixin, BeetsTestCase):
    def _show_change(self):
        """Return an unicode string representing the changes"""
        long_name = f"a{' very' * 10} long name"
        album = "another album"
        albumartist = f"another artist with {long_name}"

        def make_item(**kwargs):
            return _common.item(album=album, albumartist=albumartist, **kwargs)

        items = [
            make_item(track=1, title="first title"),
            make_item(track=2, title="", path=b"/path/to/file.mp3"),
            make_item(track=3, title="caf\xe9"),
            make_item(track=4, title=f"title with {long_name}"),
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
        source = Source.from_items(items)
        change_dist = distance(
            source.data, info, item_info_pairs, len(items) - len(info.tracks)
        )
        change_dist._penalties = {"album": [0.1], "artist": [0.1]}
        show_change(
            AlbumMatch(change_dist, info, dict(item_info_pairs)), source
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
