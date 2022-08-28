# This file is part of beets.
# Copyright 2016, J0J0 Todos.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
"""Testsuite for the M3UFile class."""


from os import path
from tempfile import mkdtemp
from shutil import rmtree
import unittest
import sys

from beets.util import bytestring_path
from beets.util.m3u import M3UFile, EmptyPlaylistError
from test._common import RSRC


class M3UFileTest(unittest.TestCase):
    """Tests the M3UFile class."""
    def test_playlist_write_empty(self):
        """Test whether saving an empty playlist file raises an error."""
        tempdir = bytestring_path(mkdtemp())
        the_playlist_file = path.join(tempdir, b'playlist.m3u8')
        m3ufile = M3UFile(the_playlist_file)
        with self.assertRaises(EmptyPlaylistError):
            m3ufile.write()
        rmtree(tempdir)

    def test_playlist_write(self):
        """Test saving ascii paths to a playlist file."""
        tempdir = bytestring_path(mkdtemp())
        the_playlist_file = path.join(tempdir, b'playlist.m3u')
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.set_contents([
            '/This/is/a/path/to_a_file.mp3',
            '/This/is/another/path/to_a_file.mp3',
        ])
        m3ufile.write()
        self.assertTrue(path.exists(the_playlist_file))
        rmtree(tempdir)

    def test_playlist_write_unicode(self):
        """Test saving unicode paths to a playlist file."""
        tempdir = bytestring_path(mkdtemp())
        the_playlist_file = path.join(tempdir, b'playlist.m3u8')
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.set_contents([
            '/This/is/å/path/to_a_file.mp3',
            '/This/is/another/path/tö_a_file.mp3',
        ])
        m3ufile.write()
        self.assertTrue(path.exists(the_playlist_file))
        rmtree(tempdir)

    def test_playlist_load_ascii(self):
        """Test loading ascii paths from a playlist file."""
        the_playlist_file = path.join(RSRC, b'playlist.m3u')
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.load()
        self.assertEqual(m3ufile.media_list[0],
                         '/This/is/a/path/to_a_file.mp3\n')

    @unittest.skipIf(sys.platform == 'win32', 'win32')
    def test_playlist_load_unicode(self):
        """Test loading unicode paths from a playlist file."""
        the_playlist_file = path.join(RSRC, b'playlist.m3u8')
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.load()
        self.assertEqual(m3ufile.media_list[0],
                         '/This/is/å/path/to_a_file.mp3\n')

    @unittest.skipUnless(sys.platform == 'win32', 'win32')
    def test_playlist_load_unicode_windows(self):
        """Test loading unicode paths from a playlist file."""
        the_playlist_file = path.join(RSRC, b'playlist_windows.m3u8')
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.load()
        self.assertEqual(m3ufile.media_list[0],
                         'x:\This\is\å\path\to_a_file.mp3\n')

    def test_playlist_load_extm3u(self):
        """Test loading a playlist with an #EXTM3U header."""
        the_playlist_file = path.join(RSRC, b'playlist.m3u')
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.load()
        self.assertTrue(m3ufile.extm3u)

    def test_playlist_load_non_extm3u(self):
        """Test loading a playlist without an #EXTM3U header."""
        the_playlist_file = path.join(RSRC, b'playlist_non_ext.m3u')
        m3ufile = M3UFile(the_playlist_file)
        m3ufile.load()
        self.assertFalse(m3ufile.extm3u)


def suite():
    """This testsuite's main function."""
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
