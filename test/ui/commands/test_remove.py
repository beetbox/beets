import os

from beets import library
from beets.test.helper import BeetsTestCase, IOMixin
from beets.ui.commands.remove import remove_items
from beets.util import MoveOperation, syspath


class RemoveTest(IOMixin, BeetsTestCase):
    def setUp(self):
        super().setUp()

        # Copy a file into the library.
        self.i = library.Item.from_path(self.resource_path)
        self.lib.add(self.i)
        self.i.move(operation=MoveOperation.COPY)

    def test_remove_items_no_delete(self):
        self.io.addinput("y")
        remove_items(self.lib, "", False, False, False)
        items = self.lib.items()
        assert len(list(items)) == 0
        assert self.i.filepath.exists()

    def test_remove_items_with_delete(self):
        self.io.addinput("y")
        remove_items(self.lib, "", False, True, False)
        items = self.lib.items()
        assert len(list(items)) == 0
        assert not self.i.filepath.exists()

    def test_remove_items_with_force_no_delete(self):
        remove_items(self.lib, "", False, False, True)
        items = self.lib.items()
        assert len(list(items)) == 0
        assert self.i.filepath.exists()

    def test_remove_items_with_force_delete(self):
        remove_items(self.lib, "", False, True, True)
        items = self.lib.items()
        assert len(list(items)) == 0
        assert not self.i.filepath.exists()

    def test_remove_items_select_with_delete(self):
        i2 = library.Item.from_path(self.resource_path)
        self.lib.add(i2)
        i2.move(operation=MoveOperation.COPY)

        for s in ("s", "y", "n"):
            self.io.addinput(s)
        remove_items(self.lib, "", False, True, False)
        items = self.lib.items()
        assert len(list(items)) == 1
        # There is probably no guarantee that the items are queried in any
        # spcecific order, thus just ensure that exactly one was removed.
        # To improve upon this, self.io would need to have the capability to
        # generate input that depends on previous output.
        num_existing = 0
        num_existing += 1 if os.path.exists(syspath(self.i.path)) else 0
        num_existing += 1 if os.path.exists(syspath(i2.path)) else 0
        assert num_existing == 1

    def test_remove_albums_select_with_delete(self):
        a1 = self.add_album_fixture()
        a2 = self.add_album_fixture()
        path1 = a1.items()[0].path
        path2 = a2.items()[0].path
        items = self.lib.items()
        assert len(list(items)) == 3

        for s in ("s", "y", "n"):
            self.io.addinput(s)
        remove_items(self.lib, "", True, True, False)
        items = self.lib.items()
        assert len(list(items)) == 2  # incl. the item from setUp()
        # See test_remove_items_select_with_delete()
        num_existing = 0
        num_existing += 1 if os.path.exists(syspath(path1)) else 0
        num_existing += 1 if os.path.exists(syspath(path2)) else 0
        assert num_existing == 1
