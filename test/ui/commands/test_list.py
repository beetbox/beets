from beets.test import _common
from beets.test.helper import BeetsTestCase, IOMixin, capture_stdout
from beets.ui.commands.list import list_func, list_items


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


class ListFuncTest(IOMixin, BeetsTestCase):
    """Tests for the list_func command function."""

    def setUp(self):
        super().setUp()
        self.item = self.add_item_fixture(title="TestItem", artist="TestArtist")

    def test_list_func_items(self):
        """Test list_func lists items by default."""

        class MockOpts:
            album = False

        opts = MockOpts()
        list_func(self.lib, opts, [])

        output = self.io.getoutput()
        assert "TestItem" in output

    def test_list_func_albums(self):
        """Test list_func lists albums when album flag is set."""
        album = self.add_album_fixture()

        class MockOpts:
            album = True

        opts = MockOpts()
        list_func(self.lib, opts, [])

        output = self.io.getoutput()
        # Should show album info, not just item title
        assert "TestItem" not in output  # Item title shouldn't appear in album list

    def test_list_func_with_query(self):
        """Test list_func passes query arguments."""
        item2 = self.add_item_fixture(title="DifferentItem", artist="DifferentArtist")

        class MockOpts:
            album = False

        opts = MockOpts()
        list_func(self.lib, opts, ["artist:TestArtist"])

        output = self.io.getoutput()
        assert "TestItem" in output
        assert "DifferentItem" not in output
