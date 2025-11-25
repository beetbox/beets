# This file is part of beets.
# Copyright 2025, Gabe Push.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

from beets import config, plugins
from beets.test.helper import PluginTestCase
from beetsplug.inline import InlinePlugin


class TestInlineRecursion(PluginTestCase):
    def test_no_recursion_when_inline_shadows_fixed_field(self):
        config["plugins"] = ["inline"]

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
        func = plugin.compile_inline("len(items)", album=True, field_name="item_count")

        album = self.add_album_fixture()
        assert func(album) == len(list(album.items()))
