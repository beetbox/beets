# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Fabrice Laporte.
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

"""Tests for the 'hidden' utility."""

from __future__ import division, absolute_import, print_function

import unittest
import sys
import tempfile
from beets.util import hidden
from beets import util
import subprocess
import errno
import ctypes


class HiddenFileTest(unittest.TestCase):
    def setUp(self):
        pass

    def test_osx_hidden(self):
        if not sys.platform == 'darwin':
            self.skipTest('sys.platform is not darwin')
            return

        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                command = ["chflags", "hidden", f.name]
                subprocess.Popen(command).wait()
            except OSError as e:
                if e.errno == errno.ENOENT:
                    self.skipTest("unable to find chflags")
                else:
                    raise e

            self.assertTrue(hidden.is_hidden(f.name))

    def test_windows_hidden(self):
        if not sys.platform == 'win32':
            self.skipTest('sys.platform is not windows')
            return

        # FILE_ATTRIBUTE_HIDDEN = 2 (0x2) from GetFileAttributes documentation.
        hidden_mask = 2

        with tempfile.NamedTemporaryFile() as f:
            # Hide the file using
            success = ctypes.windll.kernel32.SetFileAttributesW(f.name,
                                                                hidden_mask)

            if not success:
                self.skipTest("unable to set file attributes")

            self.assertTrue(hidden.is_hidden(f.name))

    def test_other_hidden(self):
        if sys.platform == 'darwin' or sys.platform == 'win32':
            self.skipTest('sys.platform is known')
            return

        with tempfile.NamedTemporaryFile(prefix='.tmp') as f:
            fn = util.bytestring_path(f.name)
            self.assertTrue(hidden.is_hidden(fn))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
