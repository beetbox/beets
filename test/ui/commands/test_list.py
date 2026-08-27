from beets.test import _common
from beets.test.helper import BeetsTestCase, IOMixin


class ListTest(IOMixin, BeetsTestCase):
    def setUp(self):
        super().setUp()
        self.item = _common.item()
        self.item.path = "xxx/yyy"
        self.lib.add(self.item)
        self.lib.add_album([self.item])

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
        stdout = self.run_with_output("list", "-f", "$path")
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
        stdout = self.run_with_output("list", "-f", "$artist - $album - $year")
        assert "the artist - the album - 0001" == stdout.strip()

    def test_list_album_format(self):
        stdout = self.run_with_output("list", "-a", "-f", "$genres")
        assert "the genre" in stdout
        assert "the album" not in stdout
