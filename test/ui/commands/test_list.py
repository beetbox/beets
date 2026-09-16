import os

import pytest

from beets.exceptions import UserError
from beets.test import _common
from beets.test.helper import BeetsTestCase, IOMixin


class ListTest(IOMixin, BeetsTestCase):
    def setUp(self):
        super().setUp()
        self.item = _common.item(
            path=os.fsencode(self.lib_path / "xxx/yyy"), flex=1
        )
        self.lib.add(self.item)
        self.lib.add_album([self.item])
        self.another_item = _common.item(
            path=os.fsencode(self.lib_path / "another/path"), flex=2
        )
        self.lib.add(self.another_item)

    def test_list_outputs_item(self):
        stdout = self.run_with_output("list")
        assert "the title" in stdout

    def test_list_unicode_query(self):
        self.item.title = "na\xefve"
        self.item.store()
        self.lib._connection().commit()

        stdout = self.run_with_output("list", "na\xefve")
        out = stdout
        assert "na\xefve" in out

    def test_list_item_path(self):
        stdout = self.run_with_output("list", "flex:1", "-f", "$path")
        assert stdout.strip() == str(self.lib_path / "xxx/yyy")

    def test_list_album_outputs_something(self):
        stdout = self.run_with_output("list", "-a")
        assert len(stdout) > 0

    def test_list_album_path(self):
        stdout = self.run_with_output("list", "-a", "-f", "$path")
        assert stdout.strip() == str(self.lib_path / "xxx")

    def test_list_album_omits_title(self):
        stdout = self.run_with_output("list", "-a")
        assert "the title" not in stdout

    def test_list_uses_track_artist(self):
        stdout = self.run_with_output("list")
        assert "the artist" in stdout
        assert "the album artist" not in stdout

    def test_list_album_uses_album_artist(self):
        stdout = self.run_with_output("list", "-a")
        assert "the artist" not in stdout
        assert "the album artist" in stdout

    def test_list_item_format_artist(self):
        stdout = self.run_with_output("list", "-f", "$artist")
        assert "the artist" in stdout

    def test_list_item_format_multiple(self):
        stdout = self.run_with_output(
            "list", "flex:1", "-f", "$artist - $album - $year"
        )
        assert stdout.strip() == "the artist - the album - 0001"

    def test_list_album_format(self):
        stdout = self.run_with_output("list", "-a", "-f", "$genres")
        assert "the genre" in stdout
        assert "the album" not in stdout

    def test_limit_query_results(self):
        args = "list", "-p"

        stdout = self.run_with_output(*args).strip()
        assert len(stdout.splitlines()) == 2

        stdout = self.run_with_output(*args, "-l", "1").strip()
        assert len(stdout.splitlines()) == 1

        with pytest.raises(UserError, match="must be a non-negative integer"):
            self.run_with_output(*args, "-l", "-1")

    def test_limit_sort_by_flex_attr(self):
        args = "list", "-p", "-l", "1"

        stdout = self.run_with_output(*args, "flex+").strip()
        assert stdout == os.fsdecode(self.item.path)

        stdout = self.run_with_output(*args, "flex-").strip()
        assert stdout == os.fsdecode(self.another_item.path)
