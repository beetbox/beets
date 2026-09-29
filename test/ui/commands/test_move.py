import shutil

from beets import library
from beets.test.helper import BeetsTestCase, IOMixin


class MoveTest(IOMixin, BeetsTestCase):
    def setUp(self):
        super().setUp()

        self.initial_item_path = self.lib_path / "srcfile"
        shutil.copy(self.resource_path, self.initial_item_path)

        # Add a file to the library but don't copy it in yet.
        self.i = library.Item.from_path(self.initial_item_path)
        self.lib.add(self.i)
        self.album = self.lib.add_album([self.i])

        # Alternate destination directory.
        self.otherdir = self.temp_path / "testotherdir"
        self.otherdir.mkdir()
        self.item_moved_to = self.otherdir / "Compilations"

    def test_move_item(self):
        self.run_command("move")
        self.i.load()
        assert b"libdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_copy_item(self):
        self.run_command("move", "-c")
        self.i.load()
        assert b"libdir" in self.i.path
        assert self.i.filepath.exists()
        assert self.initial_item_path.exists()

    def test_move_album(self):
        self.run_command("move", "-a")
        self.i.load()
        assert b"libdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_copy_album(self):
        self.run_command("move", "-a", "-c")
        self.i.load()
        assert b"libdir" in self.i.path
        assert self.i.filepath.exists()
        assert self.initial_item_path.exists()

    def test_move_item_custom_dir(self):
        self.run_command("move", "--dest", str(self.otherdir))
        self.i.load()
        assert b"testotherdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_move_album_custom_dir(self):
        self.run_command("move", "-a", "--dest", str(self.otherdir))
        self.i.load()
        assert b"testotherdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_move_album_custom_dir_timid(self):
        self.io.addinput("s")  # select
        self.io.addinput("y")  # yes
        self.run_command("move", "-a", "--dest", str(self.otherdir), "-t")
        self.i.load()
        assert b"testotherdir" in self.i.path
        assert self.i.filepath.exists()
        assert not self.initial_item_path.exists()

    def test_pretend_move_item(self):
        self.run_command("move", "--dest", str(self.otherdir), "-p")
        self.i.load()
        assert self.i.filepath == self.initial_item_path

    def test_pretend_move_album(self):
        self.run_command("move", "-a", "-p")
        self.i.load()
        assert self.i.filepath == self.initial_item_path

    def test_export_item_custom_dir(self):
        self.run_command("move", "--dest", str(self.otherdir), "-e")
        self.i.load()
        assert self.i.filepath == self.initial_item_path
        assert self.item_moved_to.exists()

    def test_export_album_custom_dir(self):
        self.run_command("move", "--dest", str(self.otherdir), "-a", "-e")
        self.i.load()
        assert self.i.filepath == self.initial_item_path
        assert self.item_moved_to.exists()

    def test_pretend_export_item(self):
        self.run_command("move", "--dest", str(self.otherdir), "-e", "-p")
        self.i.load()
        assert self.i.filepath == self.initial_item_path
        assert not self.item_moved_to.exists()

    def test_move_missing_singleton_continues(self):
        self.i.load()
        old_path = self.i.filepath
        old_path.unlink()
        self.run_command("move")
        self.i.load()
        assert self.i.filepath == old_path

    def test_move_album_with_missing_track(self):
        self.i.load()
        old_i_path = self.i.filepath
        old_i_path.unlink()

        i2_path = self.lib_path / "srcfile2"
        shutil.copy(self.resource_path, i2_path)
        i2 = library.Item.from_path(i2_path)
        self.lib.add(i2)
        i2.album_id = self.album.id
        i2.store()

        self.run_command("move", "-a")
        self.i.load()
        i2.load()
        assert self.i.filepath == old_i_path
        assert i2.filepath.is_relative_to(self.lib_path)
        assert i2.filepath.exists()

    def test_move_item_skips_missing_file(self):
        self.i.load()
        old_path = self.i.filepath
        old_path.unlink()
        self.i.move()
        assert self.i.filepath == old_path
