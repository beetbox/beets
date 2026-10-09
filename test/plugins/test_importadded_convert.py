"""Tests for the `importadded` plugin in `beet convert` scenarios."""

from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING

import pytest

from beets import plugins as beets_plugins
from beets import util

from .test_convert import ConvertCommand, ConvertPluginHelper

if TYPE_CHECKING:
    from beets.library import Item


@pytest.mark.skipif(sys.platform == "win32", reason="win32")
class TestConvertImportAdded(ConvertPluginHelper, ConvertCommand):
    """The convert command must not need to write to the source file.

    With `preserve_write_mtimes`, `importadded` re-applies `item.added`
    to the file beets just wrote. `beet convert` writes the *converted*
    file, so the plugin must leave the (possibly read-only) source file
    alone.
    """

    preload_plugin = False

    def setup_beets(self):
        super().setup_beets()
        self.config["plugins"] = ["convert", "importadded"]
        beets_plugins.load_plugins()
        self.config["importadded"] = {
            "preserve_mtimes": True,
            "preserve_write_mtimes": True,
        }
        self.item = self.add_item_fixture(ext="flac")
        self.item.added = time.time() - 60000
        self.item.store()
        self.converted = self.convert_dest / "converted.mp3"
        self.config["convert"] = {
            "paths": {"default": "converted"},
            "format": "mp3",
            "formats": {"mp3": self.tagged_copy_cmd("mp3")},
        }

    def source_mtime(self, item: Item) -> float:
        return item.filepath.stat().st_mtime

    def test_convert_does_not_touch_source_mtime(self):
        mtime_before = self.source_mtime(self.item)
        self.run_convert("--yes")
        assert self.converted.exists()
        assert self.source_mtime(self.item) == mtime_before

    def test_convert_with_readonly_source(self, monkeypatch):
        # Simulate a read-only (e.g. immutable) source file: os.utime on the
        # item's own path must not be attempted at all.
        source = util.syspath(self.item.path)
        real_utime = os.utime

        def denied(path, *args, **kwargs):
            if str(path) == str(source):
                raise PermissionError(1, "Operation not permitted", str(path))
            return real_utime(path, *args, **kwargs)

        monkeypatch.setattr("beetsplug.importadded.os.utime", denied)
        self.run_convert("--yes")
        assert self.converted.exists()
