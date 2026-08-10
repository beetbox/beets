from typing import ClassVar

from beets import config, plugins
from beets.test.helper import PluginTestHelper
from beetsplug.inline import InlinePlugin


class TestInlineRecursion(PluginTestHelper):
    plugin: ClassVar[str] = "inline"

    def test_no_recursion_when_inline_shadows_fixed_field(self):
        config["item_fields"] = {
            "track_no": (
                "f'{disc:02d}-{track:02d}' if disctotal > 1 else f'{track:02d}'"
            )
        }

        plugins._instances.clear()
        plugins.load_plugins()

        item = self.add_item_fixture(
            artist="Artist",
            album="Album",
            title="Title",
            track=1,
            disc=1,
            disctotal=1,
        )

        out = item.evaluate_template("$track_no")

        assert out == "01"

    def test_inline_function_body_item_field(self):
        plugin = InlinePlugin()
        func = plugin.compile_inline(
            "return track + 1", album=False, field_name="next_track"
        )

        item = self.add_item_fixture(track=3)
        assert func(item) == 4

    def test_inline_album_expression_uses_items(self):
        plugin = InlinePlugin()
        func = plugin.compile_inline(
            "len(items)", album=True, field_name="item_count"
        )

        album = self.add_album_fixture()
        assert func(album) == len(list(album.items()))

    def test_inline_album_expression_uses_items_via_obj(self):
        plugin = InlinePlugin()
        func = plugin.compile_inline(
            "len(db_obj.items())", album=True, field_name="item_count"
        )

        album = self.add_album_fixture()
        assert func(album) == len(list(album.items()))

    def test_inline_function_body_item_field_via_obj(self):
        plugin = InlinePlugin()
        func = plugin.compile_inline(
            "return db_obj.track + 1", album=False, field_name="next_track"
        )

        item = self.add_item_fixture(track=3)
        assert func(item) == 4

    def test_inline_obj_missing(self):
        config["plugins"] = ["inline", "missing"]

        config["album_fields"] = {"has_missing": ("bool(db_obj.missing)")}

        plugins._instances.clear()
        plugins.load_plugins()

        album = self.add_album_fixture(track_count=1)
        album.tracktotal = 3
        for item in album.items():
            item.tracktotal = 3
            item.store()
        album.store()
        assert album._get("has_missing")

    def test_inline_function_body_obj(self):
        plugin = InlinePlugin()
        func = plugin.compile_inline(
            "return db_obj.title", album=False, field_name="title_value"
        )

        item = self.add_item_fixture(track=3)
        assert func(item)
