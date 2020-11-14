# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2020, David Swarbrick.
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

"""Tests for image resizing based on filesize."""

from __future__ import division, absolute_import, print_function


import unittest
import os

from test import _common
from test.helper import TestHelper
from beets.util.artresizer import (
    ArtResizer,
    pil_resize,
    im_resize,
    get_im_version,
    get_pil_version,
)

class ArtResizerFileSizeTest(_common.TestCase, TestHelper):
    """Unittest test case for Art Resizer to a specific size, inheriting from beets helpers."""

    IMG_225x225 = os.path.join(_common.RSRC, b"abbey.jpg")
    IMG_225x225_SIZE = os.stat(IMG_225x225).st_size
    LOWER_MAX_FILESIZE = 5e3

    def setUp(self):
        """Called before each test, setting up beets."""
        self.setup_beets()

    def tearDown(self):
        """Called after each test, unloading all plugins."""
        self.teardown_beets()

    def _test_img_resize(self, resize_func):
        """Wrapper function to test resizing based on file size."""
        # Check "lower maximum filesize" is truly lower than original filesize
        self.assertLess(self.LOWER_MAX_FILESIZE, self.IMG_225x225_SIZE)

        # Shrink using given method, known dimension, max quality.
        im = resize_func(
            225,
            self.IMG_225x225,
            quality=95,
            max_filesize=self.LOWER_MAX_FILESIZE,
        )

        # check valid path returned
        self.assertTrue(os.path.exists(im))
        new_file_size = os.stat(im).st_size
        # check size has decreased
        self.assertLess(new_file_size, self.IMG_225x225_SIZE)
        # check size has decreased enough
        self.assertLess(new_file_size, self.LOWER_MAX_FILESIZE)

    def test_pil_file_resize(self):
        """Test PIL resize function is lowering file size."""
        if get_pil_version():
            self._test_img_resize(pil_resize)

    def test_im_file_resize(self):
        """Test IM resize function is lowering file size."""
        if get_im_version():
            self._test_img_resize(im_resize)


def suite():
    """Run this suite of tests."""
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == "__main__":
    unittest.main(defaultTest="suite")
