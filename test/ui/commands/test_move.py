import shutil

from beets import library
from beets.test.helper import BeetsTestCase
from beets.ui.commands.move import move_items


class MoveTest(BeetsTestCase):
    def setUp(self):
        super().setUp()

        self.initial_item_path = self.lib_path / "srcfile"
        shutil.copy(self.resource_path, self.initial_item_path)

        # Add a file to the library but don't copy it in yet.
        self.i = library.Item.from_path(self.initial_item_path)
        self.lib.add(self.i)
        self.album = self.lib.add_album([self.i])

        # Alternate destination directory.
        self.otherdir = self.temp_dir_path / "testotherdir"

    def _move(
        self,
        query=(),
        dest=None,
        copy=False,
        album=False,
        pretend=False,
        export=False,
    ):
        move_items(self.lib, dest, query, copy, album, pretend, export=export)

    def test_move_item(self):
        self._move()
        self.i.load()
        assert b"libdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_copy_item(self):
        self._move(copy=True)
        self.i.load()
        assert b"libdir" in self.i.path
        assert self.i.filepath.exists()
        assert self.initial_item_path.exists()

    def test_move_album(self):
        self._move(album=True)
        self.i.load()
        assert b"libdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_copy_album(self):
        self._move(copy=True, album=True)
        self.i.load()
        assert b"libdir" in self.i.path
        assert self.i.filepath.exists()
        assert self.initial_item_path.exists()

    def test_move_item_custom_dir(self):
        self._move(dest=self.otherdir)
        self.i.load()
        assert b"testotherdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_move_album_custom_dir(self):
        self._move(dest=self.otherdir, album=True)
        self.i.load()
        assert b"testotherdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_pretend_move_item(self):
        self._move(dest=self.otherdir, pretend=True)
        self.i.load()
        assert self.i.filepath == self.initial_item_path

    def test_pretend_move_album(self):
        self._move(album=True, pretend=True)
        self.i.load()
        assert self.i.filepath == self.initial_item_path

    def test_export_item_custom_dir(self):
        self._move(dest=self.otherdir, export=True)
        self.i.load()
        assert self.i.filepath == self.initial_item_path
        assert self.otherdir.exists()

    def test_export_album_custom_dir(self):
        self._move(dest=self.otherdir, album=True, export=True)
        self.i.load()
        assert self.i.filepath == self.initial_item_path
        assert self.otherdir.exists()

    def test_pretend_export_item(self):
        self._move(dest=self.otherdir, pretend=True, export=True)
        self.i.load()
        assert self.i.filepath == self.initial_item_path
        assert not self.otherdir.exists()
