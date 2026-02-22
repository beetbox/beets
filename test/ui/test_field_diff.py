from textwrap import dedent

import pytest

from beets.library import Item
from beets.ui import _field_diff

p = pytest.param


class TestFieldDiff:
    @pytest.fixture(autouse=True)
    def configure_color(self, config, color):
        config["ui"]["color"] = color

    @pytest.fixture(autouse=True)
    def patch_colorize(self, monkeypatch):
        """Patch to return a deterministic string format instead of ANSI codes."""
        monkeypatch.setattr(
            "beets.ui._colorize",
            lambda color_name, text: f"[{color_name}]{text}[/]",
        )

    @staticmethod
    def diff_fmt(old, new):
        return f"[text_diff_removed]{old}[/] -> [text_diff_added]{new}[/]"

    @pytest.mark.parametrize(
        "old_data, new_data, field, expected_diff",
        [
            p({"title": "foo"}, {"title": "foo"}, "title", None, id="no_change"),
            p({"bpm": 120.0}, {"bpm": 120.005}, "bpm", None, id="float_close_enough"),
            p({"bpm": 120.0}, {"bpm": 121.0}, "bpm", f"bpm: {diff_fmt('120', '121')}", id="float_changed"),
            p({"title": "foo"}, {"title": "bar"}, "title", f"title: {diff_fmt('foo', 'bar')}", id="string_full_replace"),
            p({"title": "prefix foo"}, {"title": "prefix bar"}, "title", "title: prefix [text_diff_removed]foo[/] -> prefix [text_diff_added]bar[/]", id="string_partial_change"),
            p({"year": 2000}, {"year": 2001}, "year", f"year: {diff_fmt('2000', '2001')}", id="int_changed"),
            p({}, {"genre": "Rock"}, "genre", "genre:  -> [text_diff_added]Rock[/]", id="field_added"),
            p({"genre": "Rock"}, {}, "genre", "genre: [text_diff_removed]Rock[/] -> ", id="field_removed"),
            p({"track": 1}, {"track": 2}, "track", f"track: {diff_fmt('01', '02')}", id="formatted_value_changed"),
            p({"mb_trackid": None}, {"mb_trackid": "1234"}, "mb_trackid", "mb_trackid:  -> [text_diff_added]1234[/]", id="none_to_value"),
            p({}, {"new_flex": "foo"}, "new_flex", "[text_diff_added]new_flex: foo[/]", id="flex_field_added"),
            p({"old_flex": "foo"}, {}, "old_flex", "[text_diff_removed]old_flex: foo[/]", id="flex_field_removed"),
            p({"albumtypes": ["album", "ep"]}, {"albumtypes": ["ep", "album"]}, "albumtypes", None, id="multi_value_unchanged"),
            p(
                {"albumtypes": ["ep"]},
                {"albumtypes": ["album", "compilation"]},
                "albumtypes",
                dedent("""
                    albumtypes:
                    [text_diff_removed]  - ep[/]
                    [text_diff_added]  + album[/]
                    [text_diff_added]  + compilation[/]
                """).strip(),
                id="multi_value_changed"
            ),
        ],
    )  # fmt: skip
    @pytest.mark.parametrize("color", [True], ids=["color_enabled"])
    def test_field_diff_colors(self, old_data, new_data, field, expected_diff):
        old_item = Item(**old_data)
        new_item = Item(**new_data)

        diff = _field_diff(field, old_item.formatted(), new_item.formatted())

        assert diff == expected_diff

    @pytest.mark.parametrize("color", [False], ids=["color_disabled"])
    def test_field_diff_no_color(self):
        old_item = Item(title="foo")
        new_item = Item(title="bar")

        diff = _field_diff("title", old_item.formatted(), new_item.formatted())

        assert diff == "title: foo -> bar"
