# This file is part of beets.
# Copyright 2025, Henry Oberholtzer
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

"""Tests for the 'titlecase' plugin"""

import pytest

from beets import config
from beets.test.helper import PluginTestCase
from beetsplug.titlecase import EXCLUDED_INFO_FIELDS, TitlecasePlugin


@pytest.mark.parametrize(
    "given, expected",
    [
        ("a", "A"),
        ("PENDULUM", "Pendulum"),
        ("Aaron-carl", "Aaron-Carl"),
        ("LTJ bukem", "LTJ Bukem"),
        (
            "Freaky chakra Vs. Single Cell orchestra",
            "Freaky Chakra vs. Single Cell Orchestra",
        ),
        ("(original mix)", "(Original Mix)"),
        ("ALL CAPS TITLE", "All Caps Title"),
    ],
)
def test_basic_titlecase(given, expected):
    """Assert that general behavior is as expected."""
    assert TitlecasePlugin().titlecase(given) == expected


class TitlecasePluginTest(PluginTestCase):
    plugin = "titlecase"
    preload_plugin = False

    def test_preserved_case(self):
        """Test using given strings to preserve case"""
        names_to_preserve = ["easyFun", "A.D.O.R.", "D.R.", "ABBA", "LaTeX"]
        with self.configure_plugin({"preserve": names_to_preserve}):
            config["titlecase"]["preserve"] = names_to_preserve
            for name in names_to_preserve:
                assert TitlecasePlugin().titlecase(name.lower()) == name

    def test_small_first_last(self):
        with self.configure_plugin({"small_first_last": False}):
            assert (
                TitlecasePlugin().titlecase("A Simple Trial")
                == "a Simple Trial"
            )
        with self.configure_plugin({"small_first_last": True}):
            assert (
                TitlecasePlugin().titlecase("A simple Trial")
                == "A Simple Trial"
            )

    def test_field_list_default_excluded(self):
        excluded = list(EXCLUDED_INFO_FIELDS)
        config["titlecase"]["include_fields"] = excluded
        t = TitlecasePlugin()
        for field in excluded:
            assert field not in t.fields_to_process

    def test_ui_commands(self):
        self.load_plugins("titlecase")
        tests = [
            (
                {
                    "title": "poorLy cased Title",
                    "artist": "Bad CaSE",
                    "album": "the album",
                },
                {
                    "title": "Poorly Cased Title",
                    "artist": "Bad Case",
                    "album": "The Album",
                },
                "",
            ),
            (
                {
                    "title": "poorLy cased Title",
                    "artist": "Bad CaSE",
                    "album": "the album",
                },
                {
                    "title": "poorLy cased Title",
                    "artist": "Bad Case",
                    "album": "the album",
                },
                "-e title album",
            ),
            (
                {
                    "title": "poorLy cased Title",
                    "artist": "Bad CaSE",
                    "album": "the album",
                },
                {
                    "title": "poorLy cased Title",
                    "artist": "Bad Case",
                    "album": "the album",
                },
                "-i artist",
            ),
            (
                {
                    "title": "poorLy cased Title",
                    "artist": "Bad CaSE",
                    "album": "the album",
                },
                {
                    "title": "poorLy Cased Title",
                    "artist": "Bad CaSE",
                    "album": "The Album",
                },
                "-p CaSE poorLy",
            ),
            (
                {
                    "title": "poorLy cased Title",
                    "artist": "Bad CaSE",
                    "album": "the album",
                },
                {
                    "title": "poorLy Cased Title",
                    "artist": "Bad CaSE",
                    "album": "The Album",
                },
                "-f",
            ),
        ]
        for test in tests:
            i, o, opts = test
            self.add_item(
                artist=i["artist"], album=i["album"], title=i["title"]
            )
            self.run_command("titlecase", opts)
            output = self.run_with_output("ls")
            assert output == f"{o['artist']} - {o['album']} - {o['title']}\n"
            self.run_command("rm", o["title"], "-f")

    def test_field_list_included(self):
        include_fields = ["album", "albumartist"]
        config["titlecase"]["include"] = include_fields
        t = TitlecasePlugin()
        assert t.fields_to_process == set(include_fields)

    def test_field_list_exclude(self):
        excluded = ["album", "albumartist"]
        config["titlecase"]["exclude"] = excluded
        t = TitlecasePlugin()
        for field in excluded:
            assert field not in t.fields_to_process
