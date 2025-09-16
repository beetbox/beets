"""Tests for the 'permissions' plugin."""

import os
import platform
from unittest.mock import Mock, patch

from beets.test._common import touch
from beets.test.helper import AsIsImporterMixin, ImportTestCase, PluginMixin
from beetsplug.permissions import (
    check_permissions,
    convert_perm,
    dirs_in_library,
)


class PermissionsPluginTest(AsIsImporterMixin, PluginMixin, ImportTestCase):
    plugin = "permissions"

    def setUp(self):
        super().setUp()

        self.config["permissions"] = {"file": "777", "dir": "777"}

    def test_permissions_on_album_imported(self):
        self.import_and_check_permissions()

    def test_permissions_on_item_imported(self):
        self.config["import"]["singletons"] = True
        self.import_and_check_permissions()

    def import_and_check_permissions(self):
        if platform.system() == "Windows":
            self.skipTest("permissions not available on Windows")

        track_file = os.path.join(self.import_dir, b"album", b"track_1.mp3")
        assert os.stat(track_file).st_mode & 0o777 != 511

        self.run_asis_importer()
        item = self.lib.items().get()

        paths = (item.path, *dirs_in_library(self.lib.directory, item.path))
        for path in paths:
            assert os.stat(path).st_mode & 0o777 == 511

    def test_convert_perm_from_string(self):
        assert convert_perm("10") == 8

    def test_convert_perm_from_int(self):
        assert convert_perm(10) == 8

    def test_permissions_on_set_art(self):
        self.do_set_art(True)

    @patch("os.chmod", Mock())
    def test_failing_permissions_on_set_art(self):
        self.do_set_art(False)

    def do_set_art(self, expect_success):
        if platform.system() == "Windows":
            self.skipTest("permissions not available on Windows")
        self.run_asis_importer()
        album = self.lib.albums().get()
        artpath = os.path.join(self.temp_dir, b"cover.jpg")
        touch(artpath)
        album.set_art(artpath)
        assert expect_success == check_permissions(album.artpath, 0o777)
