"""Tests for the 'permissions' plugin."""

import os
import platform
from unittest.mock import Mock, patch

import pytest

from beets.test.helper import (
    AsIsImporterMixin,
    ImportHelper,
    PathsMixin,
    PluginMixin,
)
from beetsplug.permissions import (
    check_permissions,
    convert_perm,
    dirs_in_library,
)


class TestDirsInLibrary(PathsMixin):
    @pytest.fixture
    def lib_path(self):
        return self.temp_path / "library"

    def test_dirs_in_library(self, lib_path):
        album_path = lib_path / "album"
        track_path = album_path / "sibling.mp3"

        assert set(
            dirs_in_library(os.fsencode(lib_path), os.fsencode(track_path))
        ) == {os.fsencode(album_path)}

    @pytest.mark.xfail(
        reason="dirs_in_library does not ignore sibling libraries", strict=True
    )
    def test_ignore_sibling_lib(self, lib_path):
        """Sibling libraries that start with the same prefix should be ignored."""
        sibling_lib_path = self.temp_path / "library1"
        sibling_track_path = sibling_lib_path / "album1" / "sibling.mp3"

        assert (
            set(
                dirs_in_library(
                    os.fsencode(lib_path), os.fsencode(sibling_track_path)
                )
            )
            == set()
        )


class TestPermissionsPlugin(AsIsImporterMixin, PluginMixin, ImportHelper):
    plugin = "permissions"

    def setup_beets(self):
        super().setup_beets()
        self.config["permissions"] = {"file": "777", "dir": "777"}

    def test_permissions_on_album_imported(self):
        self.import_and_check_permissions()

    def test_permissions_on_item_imported(self):
        self.config["import"]["singletons"] = True
        self.import_and_check_permissions()

    def import_and_check_permissions(self):
        if platform.system() == "Windows":
            pytest.skip("permissions not available on Windows")

        track_file = self.import_path / "album" / "track_1.mp3"
        assert track_file.stat().st_mode & 0o777 != 511

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
            pytest.skip("permissions not available on Windows")
        self.run_asis_importer()
        album = self.lib.albums().get()
        artpath = self.temp_path / "cover.jpg"
        artpath.touch()
        album.set_art(artpath)
        assert expect_success == check_permissions(album.artpath, 0o777)
