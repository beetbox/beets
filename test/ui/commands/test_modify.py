import unittest
from unittest.mock import patch

from mediafile import MediaFile

from beets import library, ui
from beets.test.helper import BeetsTestCase, IOMixin, capture_log, control_stdin
from beets.ui.commands.modify import (
    modify_func,
    modify_items,
    modify_parse_args,
    print_and_modify,
)
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

    def test_modify_items_no_changes(self):
        """Test that modify_items raises UserError when no items match query."""
        # Add item with specific title
        item = self.add_item_fixture(title="TargetTitle")

        # Should raise UserError when no items match the query
        try:
            modify_items(
                self.lib,
                {"artist": "NewArtist"},
                [],
                ["title:NonExistent"],
                True,
                False,
                False,
                False,
                True,
            )
            assert False, "Should have raised UserError"
        except ui.UserError as e:
            assert "No matching items found" in str(e)

    def test_modify_items_no_actual_changes(self):
        """Test that modify_items doesn't change items when values are the same."""
        # Remove any existing items from setUp
        for item in self.lib.items():
            item.remove()

        # Add a single item with known title
        item = self.add_item_fixture(title="SameTitle", artist="SameArtist")

        modify_items(
            self.lib,
            {"title": "SameTitle"},
            [],
            [],
            True,
            False,
            False,
            False,
            True,
        )

        # Verify the item was not modified (values stayed the same)
        item.load()
        assert item.title == "SameTitle"
        assert item.artist == "SameArtist"

    def test_modify_items_confirm_write_and_move(self):
        """Test confirm message when both write and move are enabled."""
        item = self.add_item_fixture(title="OldTitle")

        with patch("beets.ui.input_select_objects") as mock_select:
            mock_select.return_value = []
            modify_items(
                self.lib,
                {"title": "NewTitle"},
                [],
                [],
                write=True,
                move=True,
                album=False,
                confirm=True,
                inherit=True,
            )

            # Verify the confirmation message includes both move and write
            call_args = mock_select.call_args
            assert "Really modify, move and write tags" in call_args[0][0]

    def test_modify_items_confirm_write_only(self):
        """Test confirm message when only write is enabled."""
        item = self.add_item_fixture(title="OldTitle")

        with patch("beets.ui.input_select_objects") as mock_select:
            mock_select.return_value = []
            modify_items(
                self.lib,
                {"title": "NewTitle"},
                [],
                [],
                write=True,
                move=False,
                album=False,
                confirm=True,
                inherit=True,
            )

            call_args = mock_select.call_args
            assert "Really modify and write tags" in call_args[0][0]

    def test_modify_items_confirm_move_only(self):
        """Test confirm message when only move is enabled."""
        item = self.add_item_fixture(title="OldTitle")

        with patch("beets.ui.input_select_objects") as mock_select:
            mock_select.return_value = []
            modify_items(
                self.lib,
                {"title": "NewTitle"},
                [],
                [],
                write=False,
                move=True,
                album=False,
                confirm=True,
                inherit=True,
            )

            call_args = mock_select.call_args
            assert "Really modify and move" in call_args[0][0]

    def test_modify_items_confirm_neither_write_nor_move(self):
        """Test confirm message when neither write nor move is enabled."""
        item = self.add_item_fixture(title="OldTitle")

        with patch("beets.ui.input_select_objects") as mock_select:
            mock_select.return_value = []
            modify_items(
                self.lib,
                {"title": "NewTitle"},
                [],
                [],
                write=False,
                move=False,
                album=False,
                confirm=True,
                inherit=True,
            )

            call_args = mock_select.call_args
            assert call_args[0][0] == "Really modify"

    def test_modify_items_album_mode(self):
        """Test that modify_items works correctly in album mode."""
        # Remove any existing items/albums from setUp
        for item in self.lib.items():
            item.remove()
        for album in self.lib.albums():
            album.remove()

        # Add a fresh album
        album = self.add_album_fixture()
        original_album_name = album.album

        modify_items(
            self.lib,
            {"album": "NewAlbumName"},
            [],
            [],
            write=True,
            move=False,
            album=True,
            confirm=False,
            inherit=True,
        )

        # Verify album was modified
        album.load()
        assert album.album == "NewAlbumName"
        assert album.album != original_album_name

    def test_modify_items_multiple_items(self):
        """Test that modify_items modifies multiple items."""
        # Remove any existing items from setUp
        for item in self.lib.items():
            item.remove()

        # Add two new items with different artists
        item1 = self.add_item_fixture(title="Item1", artist="OldArtist")
        item2 = self.add_item_fixture(title="Item2", artist="OldArtist")

        modify_items(
            self.lib,
            {"artist": "TestArtist"},
            [],
            [],
            write=True,
            move=False,
            album=False,
            confirm=False,
            inherit=True,
        )

        # Verify both items were modified
        item1.load()
        item2.load()
        assert item1.artist == "TestArtist"
        assert item2.artist == "TestArtist"


class PrintAndModifyTest(BeetsTestCase):
    """Tests for the print_and_modify function."""

    def setUp(self):
        super().setUp()

    def test_print_and_modify_with_changes(self):
        """Test that print_and_modify returns True when changes are made."""
        item = self.add_item_fixture(title="OldTitle")
        mods = {"title": "NewTitle"}
        dels = []

        changed = print_and_modify(item, mods, dels)

        assert changed is True
        assert item.title == "NewTitle"

    def test_print_and_modify_no_changes(self):
        """Test that print_and_modify returns False when no changes are made."""
        item = self.add_item_fixture(title="SameTitle")
        mods = {"title": "SameTitle"}
        dels = []

        changed = print_and_modify(item, mods, dels)

        assert changed is False
        assert item.title == "SameTitle"

    def test_print_and_modify_delete_field(self):
        """Test that print_and_modify can delete a field."""
        item = self.add_item_fixture(title="Title")
        item.flexattr = "TestValue"
        item.store()

        mods = {}
        dels = ["flexattr"]

        changed = print_and_modify(item, mods, dels)

        assert changed is True
        assert "flexattr" not in item

    def test_print_and_modify_delete_nonexistent_field(self):
        """Test that deleting a non-existent field doesn't raise an error."""
        item = self.add_item_fixture(title="Title")
        mods = {}
        dels = ["nonexistent_field"]

        # Should not raise KeyError
        changed = print_and_modify(item, mods, dels)

        # No changes were made since field didn't exist
        assert changed is False

    def test_print_and_modify_mods_and_dels(self):
        """Test that modifications and deletions can be applied together."""
        item = self.add_item_fixture(title="OldTitle")
        item.flexattr = "ToBeDeleted"
        item.store()

        mods = {"title": "NewTitle"}
        dels = ["flexattr"]

        changed = print_and_modify(item, mods, dels)

        assert changed is True
        assert item.title == "NewTitle"
        assert "flexattr" not in item


class ModifyFuncTest(IOMixin, BeetsTestCase):
    """Tests for the modify_func command function."""

    def setUp(self):
        super().setUp()
        self.item = self.add_item_fixture(title="TestTitle")

    def test_modify_func_no_modifications_error(self):
        """Test that modify_func raises UserError when no modifications specified."""

        class MockOpts:
            write = None
            move = None
            album = False
            yes = False
            inherit = True

        opts = MockOpts()

        # Should raise UserError when no mods or dels
        try:
            modify_func(self.lib, opts, [])
            assert False, "Should have raised UserError"
        except ui.UserError as e:
            assert "no modifications specified" in str(e)

    def test_modify_func_only_query_no_modifications(self):
        """Test that modify_func raises error with only query, no modifications."""

        class MockOpts:
            write = None
            move = None
            album = False
            yes = False
            inherit = True

        opts = MockOpts()

        # Should raise UserError when only query provided
        try:
            modify_func(self.lib, opts, ["title:TestTitle"])
            assert False, "Should have raised UserError"
        except ui.UserError as e:
            assert "no modifications specified" in str(e)

    def test_modify_func_with_modifications(self):
        """Test that modify_func works with valid modifications."""

        class MockOpts:
            write = None
            move = None
            album = False
            yes = True  # Skip confirmation
            inherit = True

        opts = MockOpts()

        modify_func(self.lib, opts, ["title=ModifiedTitle"])

        # Item should be modified
        self.item.load()
        assert self.item.title == "ModifiedTitle"

    def test_modify_func_with_deletions(self):
        """Test that modify_func works with field deletions."""
        self.item.flexattr = "ToDelete"
        self.item.store()

        class MockOpts:
            write = None
            move = None
            album = False
            yes = True
            inherit = True

        opts = MockOpts()

        modify_func(self.lib, opts, ["flexattr!"])

        self.item.load()
        assert "flexattr" not in self.item

    def test_modify_func_respects_yes_flag(self):
        """Test that modify_func skips confirmation when yes=True."""

        class MockOpts:
            write = None
            move = None
            album = False
            yes = True
            inherit = True

        opts = MockOpts()

        # Should not prompt for input
        modify_func(self.lib, opts, ["title=AutoModified"])

        self.item.load()
        assert self.item.title == "AutoModified"

    def test_modify_func_respects_write_flag(self):
        """Test that modify_func passes write flag to modify_items."""

        class MockOpts:
            write = True
            move = None
            album = False
            yes = True
            inherit = True

        opts = MockOpts()

        with patch("beets.ui.commands.modify.modify_items") as mock_modify:
            modify_func(self.lib, opts, ["title=NewTitle"])

            # Verify modify_items was called with write=True
            assert mock_modify.called
            call_kwargs = mock_modify.call_args
            # write should be True (4th positional argument, index 3)
            assert call_kwargs[0][4] is True

    def test_modify_func_respects_move_flag(self):
        """Test that modify_func passes move flag to modify_items."""

        class MockOpts:
            write = None
            move = True
            album = False
            yes = True
            inherit = True

        opts = MockOpts()

        with patch("beets.ui.commands.modify.modify_items") as mock_modify:
            modify_func(self.lib, opts, ["title=NewTitle"])

            # Verify modify_items was called with move=True
            assert mock_modify.called
            call_kwargs = mock_modify.call_args
            # move should be True (5th positional argument, index 4)
            assert call_kwargs[0][5] is True

    def test_modify_func_respects_album_flag(self):
        """Test that modify_func passes album flag to modify_items."""

        class MockOpts:
            write = None
            move = None
            album = True
            yes = True
            inherit = True

        opts = MockOpts()

        with patch("beets.ui.commands.modify.modify_items") as mock_modify:
            modify_func(self.lib, opts, ["album=NewAlbum"])

            # Verify modify_items was called with album=True
            assert mock_modify.called
            call_kwargs = mock_modify.call_args
            # album should be True (6th positional argument, index 5)
            assert call_kwargs[0][6] is True

    def test_modify_func_respects_inherit_flag(self):
        """Test that modify_func passes inherit flag to modify_items."""

        class MockOpts:
            write = None
            move = None
            album = False
            yes = True
            inherit = False

        opts = MockOpts()

        with patch("beets.ui.commands.modify.modify_items") as mock_modify:
            modify_func(self.lib, opts, ["title=NewTitle"])

            # Verify modify_items was called with inherit=False
            assert mock_modify.called
            call_kwargs = mock_modify.call_args
            # inherit should be False (8th positional argument, index 7)
            assert call_kwargs[0][8] is False
