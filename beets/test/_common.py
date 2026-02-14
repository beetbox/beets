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

"""Some common functionality for beets' test cases."""

from __future__ import annotations

import os
import sys
import unittest
from contextlib import contextmanager
from typing import TYPE_CHECKING

import beets
import beets.library

# Make sure the development versions of the plugins are used
import beetsplug
from beets import importer, logging, util
from beets.ui import commands
from beets.util import syspath

if TYPE_CHECKING:
    import pytest

beetsplug.__path__ = [
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            os.path.pardir,
            os.path.pardir,
            "beetsplug",
        )
    )
]

# Test resources path.
RSRC = util.bytestring_path(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            os.path.pardir,
            os.path.pardir,
            "test",
            "rsrc",
        )
    )
)
PLUGINPATH = os.path.join(RSRC.decode(), "beetsplug")

# Propagate to root logger so the test runner can capture it
log = logging.getLogger("beets")
log.propagate = True
log.setLevel(logging.DEBUG)

# OS feature test.
HAVE_SYMLINK = sys.platform != "win32"
HAVE_HARDLINK = sys.platform != "win32"


def item(lib=None, **kwargs):
    defaults = dict(
        title="the title",
        artist="the artist",
        albumartist="the album artist",
        album="the album",
        genre="the genre",
        lyricist="the lyricist",
        composer="the composer",
        arranger="the arranger",
        grouping="the grouping",
        work="the work title",
        mb_workid="the work musicbrainz id",
        work_disambig="the work disambiguation",
        year=1,
        month=2,
        day=3,
        track=4,
        tracktotal=5,
        disc=6,
        disctotal=7,
        lyrics="the lyrics",
        comments="the comments",
        bpm=8,
        comp=True,
        length=60.0,
        bitrate=128000,
        format="FLAC",
        mb_trackid="someID-1",
        mb_albumid="someID-2",
        mb_artistid="someID-3",
        mb_albumartistid="someID-4",
        mb_releasetrackid="someID-5",
        album_id=None,
        mtime=12345,
    )
    i = beets.library.Item(**{**defaults, **kwargs})
    if lib:
        lib.add(i)
    return i


# Dummy import session.
def import_session(lib=None, loghandler=None, paths=[], query=[], cli=False):
    cls = (
        commands.import_.session.TerminalImportSession
        if cli
        else importer.ImportSession
    )
    return cls(lib, loghandler, paths, query)


# Mock I/O.


class InputError(IOError):
    def __str__(self) -> str:
        return "Attempt to read with no input provided."


class DummyIn:
    encoding = "utf-8"

    def __init__(self) -> None:
        self.buf: list[str] = []

    def add(self, s: str) -> None:
        self.buf.append(f"{s}\n")

    def close(self) -> None:
        pass

    def readline(self) -> str:
        if not self.buf:
            raise InputError

        return self.buf.pop(0)


class DummyIO:
    """Test helper that manages standard input and output."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capteesys: pytest.CaptureFixture[str],
    ) -> None:
        self._capteesys = capteesys
        self.stdin = DummyIn()

        monkeypatch.setattr("sys.stdin", self.stdin)

    def addinput(self, text: str) -> None:
        """Simulate user typing into stdin."""
        self.stdin.add(text)

    def getoutput(self) -> str:
        """Get the standard output captured so far.

        Note: it clears the internal buffer, so subsequent calls will only
        return *new* output.
        """
        # Using capteesys allows you to see output in the console if the test fails
        return self._capteesys.readouterr().out


# Utility.


def touch(path):
    open(syspath(path), "a").close()


class Bag:
    """An object that exposes a set of fields given as keyword
    arguments. Any field not found in the dictionary appears to be None.
    Used for mocking Album objects and the like.
    """

    def __init__(self, **fields):
        self.fields = fields

    def __getattr__(self, key):
        return self.fields.get(key)


# Platform mocking.


@contextmanager
def platform_windows():
    import ntpath

    old_path = os.path
    try:
        os.path = ntpath
        yield
    finally:
        os.path = old_path


@contextmanager
def platform_posix():
    import posixpath

    old_path = os.path
    try:
        os.path = posixpath
        yield
    finally:
        os.path = old_path


@contextmanager
def system_mock(name):
    import platform

    old_system = platform.system
    platform.system = lambda: name
    try:
        yield
    finally:
        platform.system = old_system


def slow_test(unused=None):
    def _id(obj):
        return obj

    if "SKIP_SLOW_TESTS" in os.environ:
        return unittest.skip("test is slow")
    return _id
