import ctypes
import os
import sys
from unittest import mock

from beets import util
from beets.test.helper import IOMixin, PluginTestHelper
from beetsplug.fetchart import FetchArtPlugin, FileSystem


class TestFetchartCli(IOMixin, PluginTestHelper):
    plugin = "fetchart"

    def setup_beets(self):
        super().setup_beets()
        self.config["fetchart"]["cover_names"] = "c\xc3\xb6ver.jpg"
        self.config["art_filename"] = "mycover"
        self.album = self.add_album()

    def cover_path(self, ext: str = "jpg"):
        return os.path.join(self.album.path, f"mycover.{ext}".encode())

    def check_cover_is_stored(self, ext: str = "jpg"):
        assert self.album["artpath"] == self.cover_path(ext)
        with open(util.syspath(self.cover_path(ext))) as f:
            assert f.read() == "IMAGE"

    def hide_file_windows(self, path: bytes) -> None:
        if sys.platform == "win32":
            hidden_mask = 2
            assert ctypes.windll.kernel32.SetFileAttributesW(
                util.syspath(path), hidden_mask
            )

    def test_set_art_from_folder(self):
        self.touch(b"c\xc3\xb6ver.jpg", dir_=self.album.path, content="IMAGE")

        self.run_command("fetchart")

        self.album.load()
        self.check_cover_is_stored()

    def test_filesystem_does_not_pick_up_folder(self):
        os.makedirs(os.path.join(self.album.path, b"mycover.jpg"))
        self.run_command("fetchart")
        self.album.load()
        assert self.album["artpath"] is None

    def test_filesystem_does_not_pick_up_ignored_file(self):
        self.touch(b"co_ver.jpg", dir_=self.album.path, content="IMAGE")
        self.config["ignore"] = ["*_*"]
        self.run_command("fetchart")
        self.album.load()
        assert self.album["artpath"] is None

    def test_filesystem_picks_up_non_ignored_file(self):
        self.touch(b"cover.jpg", dir_=self.album.path, content="IMAGE")
        self.config["ignore"] = ["*_*"]
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored()

    def test_filesystem_does_not_pick_up_hidden_file(self):
        path = self.touch(b".cover.jpg", dir_=self.album.path, content="IMAGE")
        self.hide_file_windows(path)
        self.config["ignore"] = []  # By default, ignore includes '.*'.
        self.config["ignore_hidden"] = True
        self.run_command("fetchart")
        self.album.load()
        assert self.album["artpath"] is None

    def test_filesystem_picks_up_non_hidden_file(self):
        self.touch(b"cover.jpg", dir_=self.album.path, content="IMAGE")
        self.config["ignore_hidden"] = True
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored()

    def test_filesystem_picks_up_hidden_file(self):
        path = self.touch(b".cover.jpg", dir_=self.album.path, content="IMAGE")
        self.hide_file_windows(path)
        self.config["ignore"] = []  # By default, ignore includes '.*'.
        self.config["ignore_hidden"] = False
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored()

    def test_filesystem_picks_up_webp_file(self):
        self.touch(b"cover.webp", dir_=self.album.path, content="IMAGE")
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored("webp")

    def test_filesystem_picks_up_png_file(self):
        self.touch(b"cover.png", dir_=self.album.path, content="IMAGE")
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored("png")

    def test_colorization(self):
        self.config["ui"]["color"] = True
        out = self.run_with_output("fetchart")
        assert " - the älbum: \x1b[1;31mno art found\x1b[39;49;00m\n" == out

    def test_set_art_oserror_is_handled_gracefully(self):
        """OSError (e.g. PermissionError) in set_art is logged as a warning,
        not an unhandled crash. Regression test for #6193.
        """
        self.touch(b"c\xc3\xb6ver.jpg", dir_=self.album.path, content="IMAGE")
        with mock.patch(
            "beets.library.Album.set_art",
            side_effect=PermissionError("[WinError 32] file in use"),
        ):
            out = self.run_with_output("fetchart")
        self.album.load()
        assert "error writing album art" in out
        assert self.album["artpath"] is None

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
