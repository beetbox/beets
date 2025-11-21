import os
import re
import tempfile
import unittest
from unittest.mock import Mock, patch

import pytest

from beets import autotag, config, library, ui
from beets.autotag.match import distance
from beets.test import _common
from beets.test.helper import BeetsTestCase, IOMixin
from beets.ui.commands.import_ import (
    _store_dict,
    import_files,
    import_func,
    parse_logfiles,
    paths_from_logfile,
)
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

    def test_parse_paths_from_logfile_invalid_line_no_separator(self):
        """Test that paths_from_logfile raises ValueError for lines without separator."""
        logfile_content = "invalidverb\n"  # No space separator
        logfile = os.path.join(self.temp_dir, b"logfile.log")
        with open(logfile, mode="w") as fp:
            fp.write(logfile_content)

        with pytest.raises(ValueError, match="line 1 is invalid"):
            list(paths_from_logfile(logfile))

    def test_parse_paths_from_logfile_invalid_verb(self):
        """Test that paths_from_logfile raises ValueError for unknown verb."""
        logfile_content = "unknown_verb /some/path\n"
        logfile = os.path.join(self.temp_dir, b"logfile.log")
        with open(logfile, mode="w") as fp:
            fp.write(logfile_content)

        with pytest.raises(ValueError, match="line 1 contains unknown verb"):
            list(paths_from_logfile(logfile))

    def test_parse_logfiles_malformed(self):
        """Test that parse_logfiles converts ValueError to UserError."""
        logfile_content = "invalid line\n"
        logfile = os.path.join(self.temp_dir, b"logfile.log")
        with open(logfile, mode="w") as fp:
            fp.write(logfile_content)

        with pytest.raises(ui.UserError, match="malformed logfile"):
            list(parse_logfiles([logfile]))

    def test_parse_logfiles_unreadable(self):
        """Test that parse_logfiles converts OSError to UserError."""
        nonexistent_logfile = os.path.join(self.temp_dir, b"nonexistent.log")

        with pytest.raises(ui.UserError, match="unreadable logfile"):
            list(parse_logfiles([nonexistent_logfile]))

    def test_import_files_with_log_file(self):
        """Test that import_files can handle log file configuration."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as logfile:
            logpath = logfile.name

        try:
            config["import"]["log"] = logpath
            config["import"]["quiet"] = False
            config["import"]["timid"] = False

            # Mock TerminalImportSession to avoid actual import
            with patch("beets.ui.commands.import_.TerminalImportSession") as mock_session:
                mock_instance = Mock()
                mock_session.return_value = mock_instance

                import_files(self.lib, [], None)

                # Verify session was created and run was called
                assert mock_session.called
                assert mock_instance.run.called
        finally:
            config["import"]["log"] = None
            if os.path.exists(logpath):
                os.remove(logpath)

    def test_import_files_log_file_error(self):
        """Test that import_files raises UserError when log file can't be opened."""
        config["import"]["log"] = "/invalid/path/to/log.txt"
        config["import"]["quiet"] = False
        config["import"]["timid"] = False

        with pytest.raises(ui.UserError, match="Could not open log file"):
            import_files(self.lib, [], None)

        config["import"]["log"] = None

    def test_import_files_resume_quiet_mode(self):
        """Test that resume=ask is changed to False in quiet mode."""
        config["import"]["resume"] = "ask"
        config["import"]["quiet"] = True
        config["import"]["timid"] = False

        with patch("beets.ui.commands.import_.TerminalImportSession") as mock_session:
            mock_instance = Mock()
            mock_session.return_value = mock_instance

            import_files(self.lib, [], None)

            # Verify resume was set to False
            assert config["import"]["resume"].get() is False

        # Reset config
        config["import"]["resume"] = "ask"
        config["import"]["quiet"] = False


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


class ImportFuncTest(IOMixin, BeetsTestCase):
    """Tests for the import_func command function."""

    def test_import_func_no_paths_raises_error(self):
        """Test that import_func raises error when no paths provided."""

        class MockOpts:
            library = False
            copy = False
            from_logfiles = None

        opts = MockOpts()

        with pytest.raises(ui.UserError, match="no path specified"):
            import_func(self.lib, opts, [])

    def test_import_func_nonexistent_path_raises_error(self):
        """Test that import_func raises error for nonexistent path."""

        class MockOpts:
            library = False
            copy = False
            from_logfiles = None

        opts = MockOpts()

        with pytest.raises(ui.UserError, match="no such file or directory"):
            import_func(self.lib, opts, ["/nonexistent/path"])

    def test_import_func_with_copy_flag(self):
        """Test that import_func respects copy flag."""

        class MockOpts:
            library = False
            copy = True
            from_logfiles = None

        opts = MockOpts()

        # Create a temporary directory to import
        import_dir = os.path.join(self.temp_dir, b"music")
        os.makedirs(import_dir)

        with patch("beets.ui.commands.import_.import_files") as mock_import:
            import_func(self.lib, opts, [import_dir.decode()])

            # Verify that move was set to False
            assert config["import"]["move"].get() is False
            assert mock_import.called

    def test_import_func_with_library_flag(self):
        """Test that import_func handles library mode."""

        class MockOpts:
            library = True
            copy = False
            from_logfiles = None

        opts = MockOpts()

        with patch("beets.ui.commands.import_.import_files") as mock_import:
            import_func(self.lib, opts, ["artist:Beatles"])

            # Verify import_files was called with query and empty paths
            mock_import.assert_called_once()
            call_args = mock_import.call_args
            assert call_args[0][0] == self.lib
            assert call_args[0][1] == []  # empty byte_paths
            assert call_args[0][2] == ["artist:Beatles"]  # query

    def test_import_func_from_logfile_nonexistent(self):
        """Test import_func with logfile containing nonexistent paths."""

        class MockOpts:
            library = False
            copy = False
            from_logfiles = None

        opts = MockOpts()

        # Create logfile with nonexistent path
        logfile = os.path.join(self.temp_dir, b"test.log")
        with open(logfile, "w") as f:
            f.write("skip /nonexistent/path\n")

        opts.from_logfiles = [logfile.decode()]

        # Should raise error when all paths from logfile don't exist
        with pytest.raises(ui.UserError, match="none of the paths are importable"):
            import_func(self.lib, opts, [])

    def test_import_func_from_logfile_with_existing_path(self):
        """Test import_func with logfile containing existing path."""

        class MockOpts:
            library = False
            copy = False
            from_logfiles = None

        opts = MockOpts()

        # Create a temporary directory
        import_dir = os.path.join(self.temp_dir, b"music")
        os.makedirs(import_dir)

        # Create logfile with existing path
        logfile = os.path.join(self.temp_dir, b"test.log")
        with open(logfile, "w") as f:
            f.write(f"skip {import_dir.decode()}\n")

        opts.from_logfiles = [logfile.decode()]

        with patch("beets.ui.commands.import_.import_files") as mock_import:
            import_func(self.lib, opts, [])

            # Verify import_files was called
            assert mock_import.called


class StoreDictTest(unittest.TestCase):
    """Tests for the _store_dict callback function."""

    def test_store_dict_first_value(self):
        """Test _store_dict with first key=value pair."""

        class Values:
            pass

        parser = Mock()
        parser.values = Values()

        option = Mock()
        option.dest = "set_fields"

        _store_dict(option, "--set", "artist=Beatles", parser)

        # Verify dictionary was created
        assert hasattr(parser.values, "set_fields")
        assert parser.values.set_fields == {"artist": "Beatles"}

    def test_store_dict_multiple_values(self):
        """Test _store_dict with multiple key=value pairs."""

        class Values:
            pass

        parser = Mock()
        parser.values = Values()
        parser.values.set_fields = {"artist": "Beatles"}

        option = Mock()
        option.dest = "set_fields"

        _store_dict(option, "--set", "album=Abbey Road", parser)

        # Verify value was added to existing dictionary
        assert parser.values.set_fields == {"artist": "Beatles", "album": "Abbey Road"}

    def test_store_dict_invalid_format_no_equals(self):
        """Test _store_dict with invalid format (no equals sign)."""
        parser = Mock()
        parser.values = Mock()

        option = Mock()
        option.dest = "set_fields"

        with pytest.raises(ui.UserError, match="not of the form"):
            _store_dict(option, "--set", "invalid", parser)

    def test_store_dict_invalid_format_empty_key(self):
        """Test _store_dict with empty key."""
        parser = Mock()
        parser.values = Mock()

        option = Mock()
        option.dest = "set_fields"

        with pytest.raises(ui.UserError, match="not of the form"):
            _store_dict(option, "--set", "=value", parser)

    def test_store_dict_invalid_format_empty_value(self):
        """Test _store_dict with empty value."""
        parser = Mock()
        parser.values = Mock()

        option = Mock()
        option.dest = "set_fields"

        with pytest.raises(ui.UserError, match="not of the form"):
            _store_dict(option, "--set", "key=", parser)
