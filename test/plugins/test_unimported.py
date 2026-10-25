"""Tests for the unimported plugin."""

import pytest

from beets.test.helper import IOMixin, PluginTestHelper
from beets.util import bytestring_path

_p = pytest.param


class TestUnimported(IOMixin, PluginTestHelper):
    plugin = "unimported"

    def make_file(self, relative_path: str) -> str:
        """Create an empty file under the library directory."""
        path = self.lib_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return str(path)

    def get_unimported_paths(self) -> set[str]:
        """Return the set of paths reported by the command."""
        return set(self.run_with_output("unimported").splitlines())

    def test_report_files_missing_from_the_library(self):
        item = self.add_item_fixture()
        strays = {self.make_file("stray.txt"), self.make_file("sub/stray.txt")}

        assert item.filepath.exists()
        assert self.get_unimported_paths() == strays

    def test_do_not_report_album_art(self):
        album = self.add_album()
        album.artpath = bytestring_path(self.make_file("cover.jpg"))
        album.store()
        stray = self.make_file("stray.txt")

        assert self.get_unimported_paths() == {stray}

    @pytest.mark.parametrize(
        "ignore_extension, filename",
        [
            _p("mp3", "archive.mp3", id="simple"),
            _p("tar.gz", "archive.tar.gz", id="compound"),
            _p("mp3", "archive.MP3", id="case insensitive"),
        ],
    )
    def test_ignore_extension(self, ignore_extension, filename):
        self.make_file(filename)
        unimported = self.make_file("report.txt")
        with self.configure_plugin({"ignore_extensions": [ignore_extension]}):
            assert self.get_unimported_paths() == {unimported}

    def test_ignore_subdirectory(self):
        self.make_file("data/report.txt")
        self.make_file("data/nested/report.txt")
        unimported = {self.make_file("music/report.txt")}

        with self.configure_plugin({"ignore_subdirectories": ["data"]}):
            assert self.get_unimported_paths() == unimported

    def test_do_not_ignore_partially_matching_subdirectory(self):
        unimported = {
            self.make_file("music/report.txt"),
            self.make_file("data/report.txt"),
            self.make_file("data/nested/report.txt"),
        }

        with self.configure_plugin({"ignore_subdirectories": ["dat"]}):
            assert self.get_unimported_paths() == unimported
