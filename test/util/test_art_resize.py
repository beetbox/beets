"""Tests for image resizing based on filesize."""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from beets.test import _common
from beets.test.fixtures import DummyIMBackend
from beets.test.helper import RUNNING_IN_CI, BeetsTestCase, CleanupModulesMixin
from beets.util import CommandOutput, command_output
from beets.util.artresizer import IMBackend, PILBackend

_p = pytest.param

SKIP_IMAGEMAGICK = pytest.mark.skipif(
    not IMBackend.available() and not RUNNING_IN_CI,
    reason="ImageMagick not available and not running in CI environment",
)
SKIP_PIL = pytest.mark.skipif(
    not PILBackend.available() and not RUNNING_IN_CI,
    reason="PIL not available and not running in CI",
)


class ArtResizerFileSizeTest(CleanupModulesMixin, BeetsTestCase):
    """Unittest test case for Art Resizer to a specific filesize."""

    modules = (IMBackend.__module__,)

    IMG_225x225 = _common.RSRC / "abbey.jpg"

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
            max_filesize=0.9 * os.stat(im_95_qual).st_size,
        )
        assert Path(os.fsdecode(im_a)).exists()
        # target size was achieved
        assert os.stat(im_a).st_size < os.stat(im_95_qual).st_size

        # Attempt with lower initial quality
        im_75_qual = backend.resize(
            225, self.IMG_225x225, quality=75, max_filesize=0
        )
        assert Path(os.fsdecode(im_75_qual)).exists()

        im_b = backend.resize(
            225,
            self.IMG_225x225,
            quality=95,
            max_filesize=0.9 * os.stat(im_75_qual).st_size,
        )
        assert Path(os.fsdecode(im_b)).exists()
        # Check high (initial) quality still gives a smaller filesize
        assert os.stat(im_b).st_size < os.stat(im_75_qual).st_size

    @SKIP_PIL
    def test_pil_file_resize(self):
        """Test PIL resize function is lowering file size."""
        self._test_img_resize(PILBackend())

    @SKIP_IMAGEMAGICK
    def test_im_file_resize(self):
        """Test IM resize function is lowering file size."""
        self._test_img_resize(IMBackend())

    @SKIP_PIL
    def test_pil_file_deinterlace(self):
        """Test PIL deinterlace function.

        Check if the `PILBackend.deinterlace()` function returns images
        that are non-progressive
        """
        path = PILBackend().deinterlace(self.IMG_225x225)
        from PIL import Image

        with Image.open(path) as img:
            assert "progression" not in img.info

    @SKIP_IMAGEMAGICK
    def test_im_file_deinterlace(self):
        """Test ImageMagick deinterlace function.

        Check if the `IMBackend.deinterlace()` function returns images
        that are non-progressive.
        """
        im = IMBackend()
        path = im.deinterlace(self.IMG_225x225)
        cmd = [*im.identify_cmd, "-format", "%[interlace]", os.fsdecode(path)]
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


IM_VERSIONS = {"magick": "7.1.2", "convert": "6.9.12"}


class TestIMBackendVersion:
    """Detection stops at the first binary that reports an ImageMagick version.

    Probing ``convert`` once ``magick`` has answered finds an unrelated program
    on Windows, where ``convert`` names the built-in filesystem conversion tool.
    """

    @pytest.fixture(autouse=True)
    def clear_cached_version(self):
        IMBackend._version = IMBackend._legacy = None
        yield
        IMBackend._version = IMBackend._legacy = None

    @pytest.fixture
    def installed(self, request):
        """Let only the requested ImageMagick binaries report their version."""

        def command_output(cmd):
            if (name := cmd[0]) not in request.param:
                raise subprocess.CalledProcessError(1, cmd)

            version = IM_VERSIONS[name]
            return CommandOutput(
                f"Version: ImageMagick {version}".encode(), b""
            )

        with patch("beets.util.artresizer.util.command_output", command_output):
            yield

    @pytest.mark.parametrize(
        "installed, expected", [
            _p({"magick"}, ((7, 1, 2), False), id="magick"),
            _p({"convert"}, ((6, 9, 12), True), id="convert"),
            _p({"magick", "convert"}, ((7, 1, 2), False), id="both"),
        ], indirect=["installed"],
    )  # fmt: skip
    @pytest.mark.usefixtures("installed")
    def test_version(self, expected):
        assert (IMBackend.version(), IMBackend._legacy) == expected
