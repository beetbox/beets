"""Tests for image resizing based on filesize."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from beets.test import _common
from beets.test.fixtures import DummyIMBackend
from beets.test.helper import BeetsTestCase, CleanupModulesMixin
from beets.util import command_output, syspath
from beets.util.artresizer import IMBackend, PILBackend


class ArtResizerFileSizeTest(CleanupModulesMixin, BeetsTestCase):
    """Unittest test case for Art Resizer to a specific filesize."""

    modules = (IMBackend.__module__,)

    IMG_225x225 = os.path.join(_common.RSRC, b"abbey.jpg")

    def _test_img_resize(self, backend):
        """Test resizing based on file size, given a resize_func."""
        # Check quality setting unaffected by new parameter
        im_95_qual = backend.resize(
            225, self.IMG_225x225, quality=95, max_filesize=0
        )
        # check valid path returned - max_filesize hasn't broken resize command
        assert Path(os.fsdecode(im_95_qual)).exists()

        # Attempt a lower filesize with same quality
        im_a = backend.resize(
            225,
            self.IMG_225x225,
            quality=95,
            max_filesize=0.9 * os.stat(syspath(im_95_qual)).st_size,
        )
        assert Path(os.fsdecode(im_a)).exists()
        # target size was achieved
        assert (
            os.stat(syspath(im_a)).st_size
            < os.stat(syspath(im_95_qual)).st_size
        )

        # Attempt with lower initial quality
        im_75_qual = backend.resize(
            225, self.IMG_225x225, quality=75, max_filesize=0
        )
        assert Path(os.fsdecode(im_75_qual)).exists()

        im_b = backend.resize(
            225,
            self.IMG_225x225,
            quality=95,
            max_filesize=0.9 * os.stat(syspath(im_75_qual)).st_size,
        )
        assert Path(os.fsdecode(im_b)).exists()
        # Check high (initial) quality still gives a smaller filesize
        assert (
            os.stat(syspath(im_b)).st_size
            < os.stat(syspath(im_75_qual)).st_size
        )

    @unittest.skipUnless(PILBackend.available(), "PIL not available")
    def test_pil_file_resize(self):
        """Test PIL resize function is lowering file size."""
        self._test_img_resize(PILBackend())

    @unittest.skipUnless(IMBackend.available(), "ImageMagick not available")
    def test_im_file_resize(self):
        """Test IM resize function is lowering file size."""
        self._test_img_resize(IMBackend())

    @unittest.skipUnless(PILBackend.available(), "PIL not available")
    def test_pil_file_deinterlace(self):
        """Test PIL deinterlace function.

        Check if the `PILBackend.deinterlace()` function returns images
        that are non-progressive
        """
        path = PILBackend().deinterlace(self.IMG_225x225)
        from PIL import Image

        with Image.open(path) as img:
            assert "progression" not in img.info

    @unittest.skipUnless(IMBackend.available(), "ImageMagick not available")
    def test_im_file_deinterlace(self):
        """Test ImageMagick deinterlace function.

        Check if the `IMBackend.deinterlace()` function returns images
        that are non-progressive.
        """
        im = IMBackend()
        path = im.deinterlace(self.IMG_225x225)
        cmd = [
            *im.identify_cmd,
            "-format",
            "%[interlace]",
            syspath(path, prefix=False),
        ]
        out = command_output(cmd).stdout
        assert out == b"None"

    @patch("beets.util.artresizer.util")
    def test_write_metadata_im(self, mock_util):
        """Test writing image metadata."""
        metadata = {"a": "A", "b": "B"}
        im = DummyIMBackend()
        im.write_metadata("foo", metadata)
        command = [*im.convert_cmd, *"foo -set a A -set b B foo".split()]
        mock_util.command_output.assert_called_once_with(command)
