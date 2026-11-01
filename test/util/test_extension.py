"""Tests for the file extension detection helper."""

import os
import shutil
import subprocess
from unittest.mock import patch

import pytest

from beets.test import _common
from beets.util.extension import fix_extension, remux_mpeglayer3_wav

_p = pytest.param


@pytest.fixture
def ffprobe_output(request):
    """Stub ffprobe, reporting an mp3 with the given line terminator."""
    lines = ["[FORMAT]", "format_name=mp3", "[/FORMAT]", ""]
    completed = subprocess.CompletedProcess(
        [], 0, request.param.join(lines).encode(), b""
    )
    with patch("beets.util.extension.subprocess.run", return_value=completed):
        yield


def test_remux_mpeglayer3_wav(tmp_path):
    src = _common.RSRC / "mpeglayer3.wav"
    dest = tmp_path / "mpeglayer3.wav"
    shutil.copy(src, dest)

    mp3_path = remux_mpeglayer3_wav(dest)

    assert mp3_path is not None
    assert mp3_path.suffix == ".mp3"
    assert mp3_path.exists()
    assert not dest.exists()


@pytest.mark.parametrize(
    "ffprobe_output", [_p("\n", id="lf"), _p("\r\n", id="crlf")], indirect=True
)
@pytest.mark.usefixtures("config", "ffprobe_output")
def test_fix_extension(tmp_path):
    """The detected format is appended whichever line endings ffprobe uses."""
    (source := tmp_path / "no_ext").touch()

    assert fix_extension(os.fsencode(source)) == os.fsencode(
        tmp_path / "no_ext.mp3"
    )
