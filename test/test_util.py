# This file is part of beets.
# Copyright 2015, Adrian Sampson.
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
"""Tests for base utils from the beets.util package.
"""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import sys
import re
import os
import subprocess

from mock import patch, Mock

from test._common import unittest
from test import _common
from beets import util


class UtilTest(unittest.TestCase):
    def test_open_anything(self):
        with _common.system_mock('Windows'):
            self.assertEqual(util.open_anything(), 'start')

        with _common.system_mock('Darwin'):
            self.assertEqual(util.open_anything(), 'open')

        with _common.system_mock('Tagada'):
            self.assertEqual(util.open_anything(), 'xdg-open')

    @patch('os.execlp')
    @patch('beets.util.open_anything')
    def test_interactive_open(self, mock_open, mock_execlp):
        mock_open.return_value = 'tagada'
        util.interactive_open('foo')
        mock_execlp.assert_called_once_with('tagada', 'tagada', 'foo')
        mock_execlp.reset_mock()

        util.interactive_open('foo', 'bar')
        mock_execlp.assert_called_once_with('bar', 'bar', 'foo')

    def test_sanitize_unix_replaces_leading_dot(self):
        with _common.platform_posix():
            p = util.sanitize_path(u'one/.two/three')
        self.assertFalse('.' in p)

    def test_sanitize_windows_replaces_trailing_dot(self):
        with _common.platform_windows():
            p = util.sanitize_path(u'one/two./three')
        self.assertFalse('.' in p)

    def test_sanitize_windows_replaces_illegal_chars(self):
        with _common.platform_windows():
            p = util.sanitize_path(u':*?"<>|')
        self.assertFalse(':' in p)
        self.assertFalse('*' in p)
        self.assertFalse('?' in p)
        self.assertFalse('"' in p)
        self.assertFalse('<' in p)
        self.assertFalse('>' in p)
        self.assertFalse('|' in p)

    def test_sanitize_windows_replaces_trailing_space(self):
        with _common.platform_windows():
            p = util.sanitize_path(u'one/two /three')
        self.assertFalse(' ' in p)

    def test_sanitize_path_works_on_empty_string(self):
        with _common.platform_posix():
            p = util.sanitize_path(u'')
        self.assertEqual(p, u'')

    def test_sanitize_with_custom_replace_overrides_built_in_sub(self):
        with _common.platform_posix():
            p = util.sanitize_path(u'a/.?/b', [
                (re.compile(r'foo'), u'bar'),
            ])
        self.assertEqual(p, u'a/.?/b')

    def test_sanitize_with_custom_replace_adds_replacements(self):
        with _common.platform_posix():
            p = util.sanitize_path(u'foo/bar', [
                (re.compile(r'foo'), u'bar'),
            ])
        self.assertEqual(p, u'bar/bar')

    @unittest.skip('unimplemented: #359')
    def test_sanitize_empty_component(self):
        with _common.platform_posix():
            p = util.sanitize_path(u'foo//bar', [
                (re.compile(r'^$'), u'_'),
            ])
        self.assertEqual(p, u'foo/_/bar')

    @patch('beets.util.subprocess.Popen')
    def test_command_output(self, mock_popen):
        def popen_fail(*args, **kwargs):
            m = Mock(returncode=1)
            m.communicate.return_value = None, None
            return m

        mock_popen.side_effect = popen_fail
        with self.assertRaises(subprocess.CalledProcessError) as exc_context:
            util.command_output([b"taga", b"\xc3\xa9"])
        self.assertEqual(exc_context.exception.returncode, 1)
        self.assertEqual(exc_context.exception.cmd, b"taga \xc3\xa9")


class PathConversionTest(_common.TestCase):
    def test_syspath_windows_format(self):
        with _common.platform_windows():
            path = os.path.join('a', 'b', 'c')
            outpath = util.syspath(path)
        self.assertTrue(isinstance(outpath, unicode))
        self.assertTrue(outpath.startswith(u'\\\\?\\'))

    def test_syspath_windows_format_unc_path(self):
        # The \\?\ prefix on Windows behaves differently with UNC
        # (network share) paths.
        path = '\\\\server\\share\\file.mp3'
        with _common.platform_windows():
            outpath = util.syspath(path)
        self.assertTrue(isinstance(outpath, unicode))
        self.assertEqual(outpath, u'\\\\?\\UNC\\server\\share\\file.mp3')

    def test_syspath_posix_unchanged(self):
        with _common.platform_posix():
            path = os.path.join('a', 'b', 'c')
            outpath = util.syspath(path)
        self.assertEqual(path, outpath)

    def _windows_bytestring_path(self, path):
        old_gfse = sys.getfilesystemencoding
        sys.getfilesystemencoding = lambda: 'mbcs'
        try:
            with _common.platform_windows():
                return util.bytestring_path(path)
        finally:
            sys.getfilesystemencoding = old_gfse

    def test_bytestring_path_windows_encodes_utf8(self):
        path = u'caf\xe9'
        outpath = self._windows_bytestring_path(path)
        self.assertEqual(path, outpath.decode('utf8'))

    def test_bytesting_path_windows_removes_magic_prefix(self):
        path = u'\\\\?\\C:\\caf\xe9'
        outpath = self._windows_bytestring_path(path)
        self.assertEqual(outpath, u'C:\\caf\xe9'.encode('utf8'))


class PathTruncationTest(_common.TestCase):
    def test_truncate_bytestring(self):
        with _common.platform_posix():
            p = util.truncate_path(b'abcde/fgh', 4)
        self.assertEqual(p, b'abcd/fgh')

    def test_truncate_unicode(self):
        with _common.platform_posix():
            p = util.truncate_path(u'abcde/fgh', 4)
        self.assertEqual(p, u'abcd/fgh')

    def test_truncate_preserves_extension(self):
        with _common.platform_posix():
            p = util.truncate_path(u'abcde/fgh.ext', 5)
        self.assertEqual(p, u'abcde/f.ext')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
