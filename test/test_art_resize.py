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
from beets.util import syspath
from beets.util.artresizer import (
    pil_resize,
    im_resize,
    get_im_version,
    get_pil_version,
)


class ArtResizerFileSizeTest(_common.TestCase, TestHelper):
    """Unittest test case for Art Resizer to a specific filesize."""

    IMG_225x225 = os.path.join(_common.RSRC, b"abbey.jpg")
    IMG_225x225_SIZE = os.stat(syspath(IMG_225x225)).st_size

    def setUp(self):
        """Called before each test, setting up beets."""
        self.setup_beets()

    def tearDown(self):
        """Called after each test, unloading all plugins."""
        self.teardown_beets()

    def _test_img_resize(self, resize_func):
        """Test resizing based on file size, given a resize_func."""
        # Check quality setting unaffected by new parameter
        im_unchanged = resize_func(
            225,
            self.IMG_225x225,
            quality=95,
            max_filesize=0,
        )
        # Attempt a lower filesize
        im_a = resize_func(
            225,
            self.IMG_225x225,
            quality=95,
            max_filesize=self.IMG_225x225_SIZE // 2,
        )
        # Attempt with lower initial quality
        im_b = resize_func(
            225,
            self.IMG_225x225,
            quality=75,
            max_filesize=self.IMG_225x225_SIZE // 2,
        )
        # check valid paths returned
        self.assertExists(im_unchanged)
        self.assertExists(im_a)
        self.assertExists(im_b)

        # check size has decreased enough
        # (unknown behaviour for quality-only setting)
        self.assertLess(os.stat(syspath(im_a)).st_size,
                        self.IMG_225x225_SIZE)
        self.assertLess(os.stat(syspath(im_b)).st_size,
                        self.IMG_225x225_SIZE)

    @unittest.skipUnless(get_pil_version(), "PIL not available")
    def test_pil_file_resize(self):
        """Test PIL resize function is lowering file size."""
        self._test_img_resize(pil_resize)

    @unittest.skipUnless(get_im_version(), "ImageMagick not available")
    def test_im_file_resize(self):
        """Test IM resize function is lowering file size."""
        self._test_img_resize(im_resize)


def suite():
    """Run this suite of tests."""
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == "__main__":
    unittest.main(defaultTest="suite")
