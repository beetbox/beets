# This file is part of beets.
# Copyright 2016, Thomas Scholtes.
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


import ctypes
import os
import sys

from beets import util
from beets.test.helper import IOMixin, PluginTestCase
from beetsplug.fetchart import FetchArtPlugin, FileSystem


class FetchartCliTest(IOMixin, PluginTestCase):
    plugin = "fetchart"

    def setUp(self):
        super().setUp()
        self.config["fetchart"]["cover_names"] = "c\xc3\xb6ver.jpg"
        self.config["art_filename"] = "mycover"
        self.album = self.add_album()

    def cover_path(self, ext: str = "jpg"):
        return os.path.join(self.album.path, f"mycover.{ext}".encode())

    def check_cover_is_stored(self, ext: str = "jpg"):
        assert self.album["artpath"] == self.cover_path(ext)
        with open(util.syspath(self.cover_path(ext))) as f:
            assert f.read() == "IMAGE"

    def hide_file_windows(self, ext="jpg"):
        hidden_mask = 2
        success = ctypes.windll.kernel32.SetFileAttributesW(
            self.cover_path(ext), hidden_mask
        )
        if not success:
            self.skipTest("unable to set file attributes")

    def test_set_art_from_folder(self):
        self.touch(b"c\xc3\xb6ver.jpg", dir=self.album.path, content="IMAGE")

        self.run_command("fetchart")

        self.album.load()
        self.check_cover_is_stored()

    def test_filesystem_does_not_pick_up_folder(self):
        os.makedirs(os.path.join(self.album.path, b"mycover.jpg"))
        self.run_command("fetchart")
        self.album.load()
        assert self.album["artpath"] is None

    def test_filesystem_does_not_pick_up_ignored_file(self):
        self.touch(b"co_ver.jpg", dir=self.album.path, content="IMAGE")
        self.config["ignore"] = ["*_*"]
        self.run_command("fetchart")
        self.album.load()
        assert self.album["artpath"] is None

    def test_filesystem_picks_up_non_ignored_file(self):
        self.touch(b"cover.jpg", dir=self.album.path, content="IMAGE")
        self.config["ignore"] = ["*_*"]
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored()

    def test_filesystem_does_not_pick_up_hidden_file(self):
        self.touch(b".cover.jpg", dir=self.album.path, content="IMAGE")
        if sys.platform == "win32":
            self.hide_file_windows()
        self.config["ignore"] = []  # By default, ignore includes '.*'.
        self.config["ignore_hidden"] = True
        self.run_command("fetchart")
        self.album.load()
        assert self.album["artpath"] is None

    def test_filesystem_picks_up_non_hidden_file(self):
        self.touch(b"cover.jpg", dir=self.album.path, content="IMAGE")
        self.config["ignore_hidden"] = True
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored()

    def test_filesystem_picks_up_hidden_file(self):
        self.touch(b".cover.jpg", dir=self.album.path, content="IMAGE")
        if sys.platform == "win32":
            self.hide_file_windows()
        self.config["ignore"] = []  # By default, ignore includes '.*'.
        self.config["ignore_hidden"] = False
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored()

    def test_filesystem_picks_up_webp_file(self):
        self.touch(b"cover.webp", dir=self.album.path, content="IMAGE")
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored("webp")

    def test_filesystem_picks_up_png_file(self):
        self.touch(b"cover.png", dir=self.album.path, content="IMAGE")
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored("png")

    def test_colorization(self):
        self.config["ui"]["color"] = True
        out = self.run_with_output("fetchart")
        assert " - the älbum: \x1b[1;31mno art found\x1b[39;49;00m\n" == out

    def test_sources_is_a_string(self):
        self.config["fetchart"].set({"sources": "filesystem"})
        fa = FetchArtPlugin()
        assert len(fa.sources) == 1
        assert isinstance(fa.sources[0], FileSystem)

    def test_sources_is_an_asterisk(self):
        self.config["fetchart"].set({"sources": "*"})
        fa = FetchArtPlugin()
        assert len(fa.sources) == 10

    def test_sources_is_a_string_list(self):
        self.config["fetchart"].set({"sources": ["filesystem", "coverart"]})
        fa = FetchArtPlugin()
        assert len(fa.sources) == 3

    def test_sources_is_a_mapping_list(self):
        self.config["fetchart"].set(
            {"sources": {"filesystem": "*", "coverart": "*"}}
        )
        fa = FetchArtPlugin()
        assert len(fa.sources) == 3
