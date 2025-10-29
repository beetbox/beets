from beets.test import _common
from beets.test.helper import BeetsTestCase, capture_stdout
from beets.ui.commands.list import list_items


class ListTest(BeetsTestCase):
    def setUp(self):
        super().setUp()
        self.item = _common.item()
        self.item.path = "xxx/yyy"
        self.lib.add(self.item)
        self.lib.add_album([self.item])

    def _run_list(self, query="", album=False, path=False, fmt=""):
        with capture_stdout() as stdout:
            list_items(self.lib, query, album, fmt)
        return stdout

    def test_list_outputs_item(self):
        stdout = self._run_list()
        assert "the title" in stdout.getvalue()

    def test_list_unicode_query(self):
        self.item.title = "na\xefve"
        self.item.store()
        self.lib._connection().commit()

        stdout = self._run_list(["na\xefve"])
        out = stdout.getvalue()
        assert "na\xefve" in out

    def test_list_item_path(self):
        stdout = self._run_list(fmt="$path")
        assert stdout.getvalue().strip() == "xxx/yyy"

    def test_list_album_outputs_something(self):
        stdout = self._run_list(album=True)
        assert len(stdout.getvalue()) > 0

    def test_list_album_path(self):
        stdout = self._run_list(album=True, fmt="$path")
        assert stdout.getvalue().strip() == "xxx"

    def test_list_album_omits_title(self):
        stdout = self._run_list(album=True)
        assert "the title" not in stdout.getvalue()

    def test_list_uses_track_artist(self):
        stdout = self._run_list()
        assert "the artist" in stdout.getvalue()
        assert "the album artist" not in stdout.getvalue()

    def test_list_album_uses_album_artist(self):
        stdout = self._run_list(album=True)
        assert "the artist" not in stdout.getvalue()
        assert "the album artist" in stdout.getvalue()

    def test_list_item_format_artist(self):
        stdout = self._run_list(fmt="$artist")
        assert "the artist" in stdout.getvalue()

    def test_list_item_format_multiple(self):
        stdout = self._run_list(fmt="$artist - $album - $year")
        assert "the artist - the album - 0001" == stdout.getvalue().strip()

    def test_list_album_format(self):
        stdout = self._run_list(album=True, fmt="$genre")
        assert "the genre" in stdout.getvalue()
        assert "the album" not in stdout.getvalue()
