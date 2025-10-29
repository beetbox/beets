import os
import shutil

import pytest

from beets import library, ui
from beets.test import _common
from beets.test.helper import BeetsTestCase
from beets.ui.commands.utils import do_query
from beets.util import syspath


class QueryTest(BeetsTestCase):
    def add_item(self, filename=b"srcfile", templatefile=b"full.mp3"):
        itempath = os.path.join(self.libdir, filename)
        shutil.copy(
            syspath(os.path.join(_common.RSRC, templatefile)),
            syspath(itempath),
        )
        item = library.Item.from_path(itempath)
        self.lib.add(item)
        return item, itempath

    def add_album(self, items):
        album = self.lib.add_album(items)
        return album

    def check_do_query(
        self, num_items, num_albums, q=(), album=False, also_items=True
    ):
        items, albums = do_query(self.lib, q, album, also_items)
        assert len(items) == num_items
        assert len(albums) == num_albums

    def test_query_empty(self):
        with pytest.raises(ui.UserError):
            do_query(self.lib, (), False)

    def test_query_empty_album(self):
        with pytest.raises(ui.UserError):
            do_query(self.lib, (), True)

    def test_query_item(self):
        self.add_item()
        self.check_do_query(1, 0, album=False)
        self.add_item()
        self.check_do_query(2, 0, album=False)

    def test_query_album(self):
        item, itempath = self.add_item()
        self.add_album([item])
        self.check_do_query(1, 1, album=True)
        self.check_do_query(0, 1, album=True, also_items=False)

        item, itempath = self.add_item()
        item2, itempath = self.add_item()
        self.add_album([item, item2])
        self.check_do_query(3, 2, album=True)
        self.check_do_query(0, 2, album=True, also_items=False)
