"""Testsuite for the M3UFile class."""

import sys
from pathlib import Path

import pytest

from beets.test._common import RSRC
from beets.test.helper import PathsMixin
from beets.util.m3u import EmptyPlaylistError, M3UFile


class TestM3UFile(PathsMixin):
    """Tests the M3UFile class."""

    def test_playlist_write_empty(self):
        """Test whether saving an empty playlist file raises an error."""
        the_playlist_file = self.temp_path / "playlist.m3u8"
        m3ufile = M3UFile(the_playlist_file)
        with pytest.raises(EmptyPlaylistError):
            m3ufile.write()

    def test_playlist_write(self):
        """Test saving ascii paths to a playlist file."""
        the_playlist_file = self.temp_path / "playlist.m3u8"
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.set_contents(
            [
                "/This/is/a/path/to_a_file.mp3",
                "/This/is/another/path/to_a_file.mp3",
            ]
        )
        m3ufile.write()
        assert the_playlist_file.exists()

    def test_playlist_write_unicode(self):
        """Test saving unicode paths to a playlist file."""
        the_playlist_file = self.temp_path / "playlist.m3u8"
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.set_contents(
            [
                "/This/is/å/path/to_a_file.mp3",
                "/This/is/another/path/tö_a_file.mp3",
            ]
        )
        m3ufile.write()
        assert the_playlist_file.exists()

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-style paths")
    def test_playlist_write_and_read_unicode_windows(self):
        """Test saving unicode paths to a playlist file on Windows."""
        the_playlist_file = (
            self.temp_path / "playlist_write_and_read_windows.m3u8"
        )
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.set_contents(
            [
                r"x:\This\is\å\path\to_a_file.mp3",
                r"x:\This\is\another\path\tö_a_file.mp3",
            ]
        )
        m3ufile.write()
        assert the_playlist_file.exists()
        m3ufile_read = M3UFile(the_playlist_file)
        m3ufile_read.load()
        assert (
            m3ufile.media_list[0]
            == Path("x:\\") / "This" / "is" / "å" / "path" / "to_a_file.mp3"
        )
        assert (
            m3ufile.media_list[1] == r"x:\This\is\another\path\tö_a_file.mp3"
        ), Path("x:\\") / "This" / "is" / "another" / "path" / "tö_a_file.mp3"

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-style paths")
    def test_playlist_load_ascii(self):
        """Test loading ascii paths from a playlist file."""
        the_playlist_file = RSRC / "playlist.m3u"
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.load()
        assert m3ufile.media_list[0] == "/This/is/a/path/to_a_file.mp3"

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows-style paths")
    def test_playlist_load_unicode(self):
        """Test loading unicode paths from a playlist file."""
        the_playlist_file = RSRC / "playlist.m3u8"
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.load()
        assert m3ufile.media_list[0] == "/This/is/å/path/to_a_file.mp3"

    @pytest.mark.skipif(sys.platform != "win32", reason="Unix-style paths")
    def test_playlist_load_unicode_windows(self):
        """Test loading unicode paths from a playlist file."""
        the_playlist_file = RSRC / "playlist_windows.m3u8"
        winpath = Path("x:\\") / "This" / "is" / "å" / "path" / "to_a_file.mp3"
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.load()
        assert m3ufile.media_list[0] == str(winpath)

    def test_playlist_load_extm3u(self):
        """Test loading a playlist with an #EXTM3U header."""
        the_playlist_file = RSRC / "playlist.m3u"
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.load()
        assert m3ufile.extm3u

    def test_playlist_load_non_extm3u(self):
        """Test loading a playlist without an #EXTM3U header."""
        the_playlist_file = RSRC / "playlist_non_ext.m3u"
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.load()
        assert not m3ufile.extm3u
