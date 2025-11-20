from beets.test.helper import BeetsTestCase


class WriteTest(BeetsTestCase):
    def write_cmd(self, *args):
        return self.run_with_output("write", *args)

    def test_update_mtime(self):
        item = self.add_item_fixture()
        item["title"] = "a new title"
        item.store()

        item = self.lib.items().get()
        assert item.mtime == 0

        self.write_cmd()
        item = self.lib.items().get()
        assert item.mtime == item.current_mtime()

    def test_non_metadata_field_unchanged(self):
        """Changing a non-"tag" field like `bitrate` and writing should
        have no effect.
        """
        # An item that starts out "clean".
        item = self.add_item_fixture()
        item.read()

        # ... but with a mismatched bitrate.
        item.bitrate = 123
        item.store()

        output = self.write_cmd()

        assert output == ""

    def test_write_metadata_field(self):
        item = self.add_item_fixture()
        item.read()
        old_title = item.title

        item.title = "new title"
        item.store()

        output = self.write_cmd()

        assert f"{old_title} -> new title" in output
