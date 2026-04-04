# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""A tool that finds an extension for files without one"""

import os
import subprocess
from logging import Logger
from pathlib import Path

import beets
from beets import util

logger = Logger.info

PathBytes = bytes
PATH_SEP: bytes = util.bytestring_path(os.sep)

# a list of audio formats I got from wikipedia https://en.wikipedia.org/wiki/Audio_file_format
AUDIO_EXTENSIONS = {
    "3gp",
    "aa",
    "aac",
    "aax",
    "act",
    "aiff",
    "alac",
    "amr",
    "ape",
    "au",
    "awb",
    "dss",
    "dvf",
    "flac",
    "gsm",
    "iklax",
    "ivs",
    "m4a",
    "m4b",
    "m4p",
    "mmf",
    "movpkg",
    "mp1",
    "mp2",
    "mp3",
    "mpc",
    "msv",
    "nmf",
    "ogg",
    "oga",
    "mogg",
    "opus",
    "ra",
    "rm",
    "raw",
    "rf64",
    "sln",
    "tta",
    "voc",
    "vox",
    "wav",
    "wma",
    "wv",
    "webm",
    "8svx",
    "cda",
}


def fix_extension(path_bytes: PathBytes, logger: Logger | None = None):
    """Return the `path` after adding an appropriate extension if needed.

    If the file already has an extension, return as-is.
    If the file has no extension, try to find the format using ffprobe.
    If the file is not a music format, return as-is.
    If the format is found, return path with extension.
    """
    path = Path(os.fsdecode(path_bytes))
    # if there is an extension, return unchanged
    if path.suffix != "":
        return path_bytes

    # no extension detected
    # use ffprobe to find the format
    formats = []
    shell = os.name == "nt"
    if (
        subprocess.run(
            ["ffprobe", "-version"], capture_output=True, shell=shell
        ).stderr.decode("utf-8")
        != ""
    ):
        if logger:
            logger.error("ffprobe needed to determine file extension")
    output = subprocess.run(
        [
            "ffprobe",
            "-hide_banner",
            "-loglevel",
            "fatal",
            "-show_format",
            "--",
            str(path),
        ],
        capture_output=True,
        shell=shell,
    )
    out = output.stdout.decode("utf-8")
    err = output.stderr.decode("utf-8")
    if err != "":
        if logger:
            logger.error("Error with ffprobe\n", err)
    for line in out.split("\n"):
        if line.startswith("format_name="):
            formats = line.split("=")[1].split(",")
    detected_format = ""
    # The first format from ffprobe that is on this list is taken
    for f in formats:
        if f in AUDIO_EXTENSIONS:
            detected_format = f
            break

    # if ffprobe can't find a format, the file is prob not music
    if detected_format == "":
        return path_bytes

    # cp and add ext. If already exist, use that file
    # assume, for example, the only diff between 'asdf.mp3' and 'asdf' is format
    new_path = path.with_suffix("." + detected_format)
    if not new_path.exists():
        if beets.config["import"]["fix_ext_inplace"]:
            util.move(bytes(path), bytes(new_path))
        else:
            util.copy(bytes(path), bytes(new_path))
    else:
        if logger:
            logger.info("Import file with matching format to original target")
    return new_path
