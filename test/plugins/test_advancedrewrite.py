# This file is part of beets.
# Copyright 2023, Max Rumpf.
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

"""Test the advancedrewrite plugin for various configurations.
"""

import unittest

from beets.test.helper import BeetsTestCase
from beets.ui import UserError

PLUGIN_NAME = "advancedrewrite"


class AdvancedRewritePluginTest(BeetsTestCase):
    def setUp(self):
        self.setup_beets()

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_simple_rewrite_example(self):
        self.config[PLUGIN_NAME] = [
            {"artist ODD EYE CIRCLE": "이달의 소녀 오드아이써클"},
        ]
        self.load_plugins(PLUGIN_NAME)

        item = self.add_item(
            title="Uncover",
            artist="ODD EYE CIRCLE",
            albumartist="ODD EYE CIRCLE",
            album="Mix & Match",
        )

        self.assertEqual(item.artist, "이달의 소녀 오드아이써클")

    def test_advanced_rewrite_example(self):
        self.config[PLUGIN_NAME] = [
            {
                "match": "mb_artistid:dec0f331-cb08-4c8e-9c9f-aeb1f0f6d88c year:..2022",
                "replacements": {
                    "artist": "이달의 소녀 오드아이써클",
                    "artist_sort": "LOONA / ODD EYE CIRCLE",
                },
            },
        ]
        self.load_plugins(PLUGIN_NAME)

        item_a = self.add_item(
            title="Uncover",
            artist="ODD EYE CIRCLE",
            albumartist="ODD EYE CIRCLE",
            artist_sort="ODD EYE CIRCLE",
            albumartist_sort="ODD EYE CIRCLE",
            album="Mix & Match",
            mb_artistid="dec0f331-cb08-4c8e-9c9f-aeb1f0f6d88c",
            year=2017,
        )
        item_b = self.add_item(
            title="Air Force One",
            artist="ODD EYE CIRCLE",
            albumartist="ODD EYE CIRCLE",
            artist_sort="ODD EYE CIRCLE",
            albumartist_sort="ODD EYE CIRCLE",
            album="ODD EYE CIRCLE <Version Up>",
            mb_artistid="dec0f331-cb08-4c8e-9c9f-aeb1f0f6d88c",
            year=2023,
        )

        # Assert that all replacements were applied to item_a
        self.assertEqual("이달의 소녀 오드아이써클", item_a.artist)
        self.assertEqual("LOONA / ODD EYE CIRCLE", item_a.artist_sort)
        self.assertEqual("LOONA / ODD EYE CIRCLE", item_a.albumartist_sort)

        # Assert that no replacements were applied to item_b
        self.assertEqual("ODD EYE CIRCLE", item_b.artist)

    def test_advanced_rewrite_example_with_multi_valued_field(self):
        self.config[PLUGIN_NAME] = [
            {
                "match": "artist:배유빈 feat. 김미현",
                "replacements": {
                    "artists": ["유빈", "미미"],
                },
            },
        ]
        self.load_plugins(PLUGIN_NAME)

        item = self.add_item(
            artist="배유빈 feat. 김미현",
            artists=["배유빈", "김미현"],
        )

        self.assertEqual(item.artists, ["유빈", "미미"])

    def test_fail_when_replacements_empty(self):
        self.config[PLUGIN_NAME] = [
            {
                "match": "artist:A",
                "replacements": {},
            },
        ]
        with self.assertRaises(
            UserError,
            msg="Advanced rewrites must have at least one replacement",
        ):
            self.load_plugins(PLUGIN_NAME)

    def test_fail_when_rewriting_single_valued_field_with_list(self):
        self.config[PLUGIN_NAME] = [
            {
                "match": "artist:'A & B'",
                "replacements": {
                    "artist": ["C", "D"],
                },
            },
        ]
        with self.assertRaises(
            UserError,
            msg="Field artist is not a multi-valued field but a list was given: C, D",
        ):
            self.load_plugins(PLUGIN_NAME)

    def test_combined_rewrite_example(self):
        self.config[PLUGIN_NAME] = [
            {"artist A": "B"},
            {
                "match": "album:'C'",
                "replacements": {
                    "artist": "D",
                },
            },
        ]
        self.load_plugins(PLUGIN_NAME)

        item = self.add_item(
            artist="A",
            albumartist="A",
        )
        self.assertEqual(item.artist, "B")

        item = self.add_item(
            artist="C",
            albumartist="C",
            album="C",
        )
        self.assertEqual(item.artist, "D")


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == "__main__":
    unittest.main(defaultTest="suite")
