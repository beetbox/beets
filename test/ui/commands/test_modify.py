import pytest
from mediafile import MediaFile

from beets import logging
from beets.exceptions import UserError
from beets.test.helper import BeetsTestCase, IOMixin, TestHelper
from beets.ui.commands.modify import ModifyOperation, modify_parse_args
from beets.util import syspath

_p = pytest.param


class ModifyHelper(IOMixin):
    def modify_inp(self, inp: list[str], *args):
        for chat in inp:
            self.io.addinput(chat)
        self.run_command("modify", *args)

    def modify(self, *args):
        self.modify_inp(["y"], *args)


class ModifyTest(ModifyHelper, BeetsTestCase):
    def setUp(self):
        super().setUp()
        self.album = self.add_album_fixture()
        [self.item] = self.album.items()

    # Item tests

    def test_modify_item(self):
        self.modify("title=newTitle")
        item = self.lib.items().get()
        assert item.title == "newTitle"

    def test_modify_item_abort(self):
        item = self.lib.items().get()
        title = item.title
        self.modify_inp(["n"], "title=newTitle")
        item = self.lib.items().get()
        assert item.title == title

    def test_modify_item_no_change(self):
        title = "Tracktitle"
        item = self.add_item_fixture(title=title)
        self.modify_inp(["y"], "title", f"title={title}")
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
        for i in range(10):
            self.add_item_fixture(
                title=f"{title}{i}", artist=original_artist, album=album
            )
        self.modify_inp(
            ["s", "y", "y", "y", "n", "n", "y", "y", "y", "y", "n"],
            title,
            f"artist={new_artist}",
        )
        original_items = self.lib.items(f"artist:{original_artist}")
        new_items = self.lib.items(f"artist:{new_artist}")
        assert len(list(original_items)) == 3
        assert len(list(new_items)) == 7

    def test_modify_formatted(self):
        for i in range(3):
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

    def test_album_modify_artists_not_split(self):
        self.modify("--album", "artists=Charli XCX")
        for item in self.lib.items():
            assert item.artists == ["Charli XCX"], (
                f"artists should be a list with one element, "
                f"got {item.artists!r}"
            )

    def test_album_modify_genres_not_split(self):
        self.modify("--album", "genres=Rock")
        for item in self.lib.items():
            assert item.genres == ["Rock"], (
                f"genres should be a list with one element, got {item.genres!r}"
            )

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

    def test_delete_initial_key_tag(self):
        item = self.add_item_fixture()
        item.initial_key = "C#m"
        item.write()
        item.store()

        mediafile = MediaFile(syspath(item.path))
        assert mediafile.initial_key == "C#m"

        self.modify("initial_key!")
        mediafile = MediaFile(syspath(item.path))
        assert mediafile.initial_key is None

    def test_arg_parsing_colon_query(self):
        query, mods, _ = modify_parse_args(
            ["title:oldTitle", "title=newTitle"], is_album=False
        )
        assert query == ["title:oldTitle"]
        assert mods == {"title": ModifyOperation(None, "newTitle")}

    def test_arg_parsing_delete(self):
        query, _, dels = modify_parse_args(
            ["title:oldTitle", "title!"], is_album=False
        )
        assert query == ["title:oldTitle"]
        assert dels == ["title"]

    def test_arg_parsing_query_with_exclaimation(self):
        query, mods, _ = modify_parse_args(
            ["title:oldTitle!", "title=newTitle!"], is_album=False
        )
        assert query == ["title:oldTitle!"]
        assert mods == {"title": ModifyOperation(None, "newTitle!")}

    def test_arg_parsing_equals_in_value(self):
        query, mods, _ = modify_parse_args(
            ["title:foo=bar", "title=newTitle"], is_album=False
        )
        assert query == ["title:foo=bar"]
        assert mods == {"title": ModifyOperation(None, "newTitle")}


class TestMultiValue(ModifyHelper, TestHelper):
    @pytest.fixture
    def item(self):
        album = self.add_album_fixture()
        [item] = album.items()
        return item

    @pytest.mark.parametrize(
        "initial_genres, modify_arg, expected_genres",
        [
            _p([], "genres=Jazz; Blues", ["Jazz", "Blues"], id="assign"),
            _p(
                ["Jazz", "Blues"],
                "genres+=Funk",
                ["Jazz", "Blues", "Funk"],
                id="append",
            ),
            _p(
                ["Jazz", "Funk"],
                "genres+=Funk",
                ["Jazz", "Funk"],
                id="append-duplicate",
            ),
            _p(
                ["Jazz", "Blues", "Funk"],
                "genres-=Blues",
                ["Jazz", "Funk"],
                id="remove-exact",
            ),
            _p(
                ["Jazz", "Blues Rock", "Blues"],
                "genres-=Blues",
                ["Jazz", "Blues Rock"],
                id="remove-no-partial-match",
            ),
            _p(
                ["Jazz", "Blues"],
                "genres+=Funk; Soul",
                ["Jazz", "Blues", "Funk", "Soul"],
                id="append-preserves-order",
            ),
        ],
    )
    def test_modify_multi_value(
        self, item, initial_genres, modify_arg, expected_genres
    ):
        item.genres = initial_genres
        item.store()

        self.modify("--nowrite", "--nomove", modify_arg)
        item.load()
        assert item.genres == expected_genres

    def test_modify_scalar_operator_error(self):
        with pytest.raises(UserError, match="field 'title' does not support"):
            self.modify("--nowrite", "--nomove", "title+=foo")


@pytest.mark.parametrize(
    "is_album, legacy_field, list_field",
    [
        _p(True, "genre", "genres", id="album-genre"),
        _p(False, "genre", "genres", id="item-genre"),
        _p(False, "composer", "composers", id="item-composer"),
    ],
)
def test_arg_parsing_rewrites_legacy_list_fields(
    is_album, legacy_field, list_field, caplog
):
    with caplog.at_level(logging.WARNING, logger="beets"):
        query, mods, dels = modify_parse_args(
            [f"{legacy_field}=value1; value2"], is_album=is_album
        )

    assert query == []
    assert mods == {list_field: ModifyOperation(None, "value1; value2")}
    assert dels == []
    assert caplog.records, "No log records were captured"
    assert len(caplog.records) == 1
    message = str(caplog.records[0].msg)
    assert f"The '{legacy_field}' field is deprecated" in message
    assert f"Use '{list_field}' (separate values by '; ') instead." in message
