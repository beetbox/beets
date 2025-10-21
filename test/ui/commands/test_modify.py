import unittest

from mediafile import MediaFile

from beets.test.helper import BeetsTestCase, control_stdin
from beets.ui.commands.modify import modify_parse_args
from beets.util import syspath


class ModifyTest(BeetsTestCase):
    def setUp(self):
        super().setUp()
        self.album = self.add_album_fixture()
        [self.item] = self.album.items()

    def modify_inp(self, inp, *args):
        with control_stdin(inp):
            self.run_command("modify", *args)

    def modify(self, *args):
        self.modify_inp("y", *args)

    # Item tests

    def test_modify_item(self):
        self.modify("title=newTitle")
        item = self.lib.items().get()
        assert item.title == "newTitle"

    def test_modify_item_abort(self):
        item = self.lib.items().get()
        title = item.title
        self.modify_inp("n", "title=newTitle")
        item = self.lib.items().get()
        assert item.title == title

    def test_modify_item_no_change(self):
        title = "Tracktitle"
        item = self.add_item_fixture(title=title)
        self.modify_inp("y", "title", f"title={title}")
        item = self.lib.items(title).get()
        assert item.title == title

    def test_modify_write_tags(self):
        self.modify("title=newTitle")
        item = self.lib.items().get()
        item.read()
        assert item.title == "newTitle"

    def test_modify_dont_write_tags(self):
        self.modify("--nowrite", "title=newTitle")
        item = self.lib.items().get()
        item.read()
        assert item.title != "newTitle"

    def test_move(self):
        self.modify("title=newTitle")
        item = self.lib.items().get()
        assert b"newTitle" in item.path

    def test_not_move(self):
        self.modify("--nomove", "title=newTitle")
        item = self.lib.items().get()
        assert b"newTitle" not in item.path

    def test_no_write_no_move(self):
        self.modify("--nomove", "--nowrite", "title=newTitle")
        item = self.lib.items().get()
        item.read()
        assert b"newTitle" not in item.path
        assert item.title != "newTitle"

    def test_update_mtime(self):
        item = self.item
        old_mtime = item.mtime

        self.modify("title=newTitle")
        item.load()
        assert old_mtime != item.mtime
        assert item.current_mtime() == item.mtime

    def test_reset_mtime_with_no_write(self):
        item = self.item

        self.modify("--nowrite", "title=newTitle")
        item.load()
        assert 0 == item.mtime

    def test_selective_modify(self):
        title = "Tracktitle"
        album = "album"
        original_artist = "composer"
        new_artist = "coverArtist"
        for i in range(0, 10):
            self.add_item_fixture(
                title=f"{title}{i}", artist=original_artist, album=album
            )
        self.modify_inp(
            "s\ny\ny\ny\nn\nn\ny\ny\ny\ny\nn", title, f"artist={new_artist}"
        )
        original_items = self.lib.items(f"artist:{original_artist}")
        new_items = self.lib.items(f"artist:{new_artist}")
        assert len(list(original_items)) == 3
        assert len(list(new_items)) == 7

    def test_modify_formatted(self):
        for i in range(0, 3):
            self.add_item_fixture(
                title=f"title{i}", artist="artist", album="album"
            )
        items = list(self.lib.items())
        self.modify("title=${title} - append")
        for item in items:
            orig_title = item.title
            item.load()
            assert item.title == f"{orig_title} - append"

    # Album Tests

    def test_modify_album(self):
        self.modify("--album", "album=newAlbum")
        album = self.lib.albums().get()
        assert album.album == "newAlbum"

    def test_modify_album_write_tags(self):
        self.modify("--album", "album=newAlbum")
        item = self.lib.items().get()
        item.read()
        assert item.album == "newAlbum"

    def test_modify_album_dont_write_tags(self):
        self.modify("--album", "--nowrite", "album=newAlbum")
        item = self.lib.items().get()
        item.read()
        assert item.album == "the album"

    def test_album_move(self):
        self.modify("--album", "album=newAlbum")
        item = self.lib.items().get()
        item.read()
        assert b"newAlbum" in item.path

    def test_album_not_move(self):
        self.modify("--nomove", "--album", "album=newAlbum")
        item = self.lib.items().get()
        item.read()
        assert b"newAlbum" not in item.path

    def test_modify_album_formatted(self):
        item = self.lib.items().get()
        orig_album = item.album
        self.modify("--album", "album=${album} - append")
        item.load()
        assert item.album == f"{orig_album} - append"

    # Misc

    def test_write_initial_key_tag(self):
        self.modify("initial_key=C#m")
        item = self.lib.items().get()
        mediafile = MediaFile(syspath(item.path))
        assert mediafile.initial_key == "C#m"

    def test_set_flexattr(self):
        self.modify("flexattr=testAttr")
        item = self.lib.items().get()
        assert item.flexattr == "testAttr"

    def test_remove_flexattr(self):
        item = self.lib.items().get()
        item.flexattr = "testAttr"
        item.store()

        self.modify("flexattr!")
        item = self.lib.items().get()
        assert "flexattr" not in item

    @unittest.skip("not yet implemented")
    def test_delete_initial_key_tag(self):
        item = self.lib.items().get()
        item.initial_key = "C#m"
        item.write()
        item.store()

        mediafile = MediaFile(syspath(item.path))
        assert mediafile.initial_key == "C#m"

        self.modify("initial_key!")
        mediafile = MediaFile(syspath(item.path))
        assert mediafile.initial_key is None

    def test_arg_parsing_colon_query(self):
        (query, mods, dels) = modify_parse_args(
            ["title:oldTitle", "title=newTitle"]
        )
        assert query == ["title:oldTitle"]
        assert mods == {"title": "newTitle"}

    def test_arg_parsing_delete(self):
        (query, mods, dels) = modify_parse_args(["title:oldTitle", "title!"])
        assert query == ["title:oldTitle"]
        assert dels == ["title"]

    def test_arg_parsing_query_with_exclaimation(self):
        (query, mods, dels) = modify_parse_args(
            ["title:oldTitle!", "title=newTitle!"]
        )
        assert query == ["title:oldTitle!"]
        assert mods == {"title": "newTitle!"}

    def test_arg_parsing_equals_in_value(self):
        (query, mods, dels) = modify_parse_args(
            ["title:foo=bar", "title=newTitle"]
        )
        assert query == ["title:foo=bar"]
        assert mods == {"title": "newTitle"}
