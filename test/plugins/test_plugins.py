# test/plugins/test_plugins.py

from beets import config, plugins
from beets.test.helper import PluginTestCase


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
