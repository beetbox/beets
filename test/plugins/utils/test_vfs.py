"""Tests for the virtual filesystem builder.."""

from beets.test import _common
from beets.test.helper import BeetsTestCase
from beetsplug._utils import vfs


class VFSTest(BeetsTestCase):
    def setUp(self):
        super().setUp()
        self.lib.path_formats = [
            ("default", "albums/$album/$title"),
            ("singleton:true", "tracks/$artist/$title"),
        ]
        self.lib.add(_common.item())
        self.lib.add_album([_common.item()])
        self.tree = vfs.libtree(self.lib)

    def test_singleton_item(self):
        assert (
            self.tree.dirs["tracks"].dirs["the artist"].files["the title"] == 1
        )

    def test_album_item(self):
        assert (
            self.tree.dirs["albums"].dirs["the album"].files["the title"] == 2
        )
