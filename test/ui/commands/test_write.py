import re
import sys

import pytest

from beets.test.helper import BeetsTestCase, IOMixin


class WriteTest(IOMixin, BeetsTestCase):
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

    def test_progress_bar_keeps_output_on_separate_lines(self):
        """Printed changes must not end up on the progress bar's line."""
        item = self.add_item_fixture()
        item.read()
        old_title = item.title
        item.title = "new title"
        item.store()

        with pytest.MonkeyPatch.context() as mp:
            for stream in (sys.stdout, sys.stderr):
                mp.setattr(stream, "isatty", lambda: True, raising=False)
            output = self.write_cmd()

        lines = re.split(
            r"[\r\n]", re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", output)
        )
        bar_lines = [line for line in lines if "Writing items..." in line]
        assert bar_lines
        assert not any(old_title in line for line in bar_lines)
        assert f"  title: {old_title} -> new title" in lines
