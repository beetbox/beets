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


import unittest
import os

from test import _common
from test.helper import TestHelper
from beets.util import command_output, syspath
from beets.util.artresizer import (
    IMBackend,
    PILBackend,
    pil_resize,
    im_resize,
    pil_deinterlace,
    im_deinterlace,
)


class DummyIMBackend(IMBackend):
    """An `IMBackend` which pretends that ImageMagick is available, and has
    a sufficiently recent version to support image comparison.
    """
    def __init__(self):
        self.version = (7, 0, 0)
        self.legacy = False
        self.convert_cmd = ['magick']
        self.identify_cmd = ['magick', 'identify']
        self.compare_cmd = ['magick', 'compare']


class DummyPILBackend(PILBackend):
    """An `PILBackend` which pretends that PIL is available.
    """
    def __init__(self):
        pass


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

    def _test_img_resize(self, backend, resize_func):
        """Test resizing based on file size, given a resize_func."""
        # Check quality setting unaffected by new parameter
        im_95_qual = resize_func(
            backend,
            225,
            self.IMG_225x225,
            quality=95,
            max_filesize=0,
        )
        # check valid path returned - max_filesize hasn't broken resize command
        self.assertExists(im_95_qual)

        # Attempt a lower filesize with same quality
        im_a = resize_func(
            backend,
            225,
            self.IMG_225x225,
            quality=95,
            max_filesize=0.9 * os.stat(syspath(im_95_qual)).st_size,
        )
        self.assertExists(im_a)
        # target size was achieved
        self.assertLess(os.stat(syspath(im_a)).st_size,
                        os.stat(syspath(im_95_qual)).st_size)

        # Attempt with lower initial quality
        im_75_qual = resize_func(
            backend,
            225,
            self.IMG_225x225,
            quality=75,
            max_filesize=0,
        )
        self.assertExists(im_75_qual)

        im_b = resize_func(
            backend,
            225,
            self.IMG_225x225,
            quality=95,
            max_filesize=0.9 * os.stat(syspath(im_75_qual)).st_size,
        )
        self.assertExists(im_b)
        # Check high (initial) quality still gives a smaller filesize
        self.assertLess(os.stat(syspath(im_b)).st_size,
                        os.stat(syspath(im_75_qual)).st_size)

    @unittest.skipUnless(PILBackend.available(), "PIL not available")
    def test_pil_file_resize(self):
        """Test PIL resize function is lowering file size."""
        self._test_img_resize(PILBackend(), pil_resize)

    @unittest.skipUnless(IMBackend.available(), "ImageMagick not available")
    def test_im_file_resize(self):
        """Test IM resize function is lowering file size."""
        self._test_img_resize(IMBackend(), im_resize)

    @unittest.skipUnless(PILBackend.available(), "PIL not available")
    def test_pil_file_deinterlace(self):
        """Test PIL deinterlace function.

        Check if pil_deinterlace function returns images
        that are non-progressive
        """
        path = pil_deinterlace(PILBackend(), self.IMG_225x225)
        from PIL import Image
        with Image.open(path) as img:
            self.assertFalse('progression' in img.info)

    @unittest.skipUnless(IMBackend.available(), "ImageMagick not available")
    def test_im_file_deinterlace(self):
        """Test ImageMagick deinterlace function.

        Check if im_deinterlace function returns images
        that are non-progressive.
        """
        im = IMBackend()
        path = im_deinterlace(im, self.IMG_225x225)
        cmd = im.identify_cmd + [
            '-format', '%[interlace]', syspath(path, prefix=False),
        ]
        out = command_output(cmd).stdout
        self.assertTrue(out == b'None')


def suite():
    """Run this suite of tests."""
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == "__main__":
    unittest.main(defaultTest="suite")
