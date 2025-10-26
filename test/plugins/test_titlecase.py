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
from beets.library import Item
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


titlecase_test_cases = [
    {
        "config": {
            "preserve": ["D'Angelo"],
            "fields": ["artist", "albumartist", "mb_albumid"],
            "force_lowercase": False,
            "small_first_last": True,
        },
        "item": Item(
            artist="d'angelo and the vanguard",
            mb_albumid="ab140e13-7b36-402a-a528-b69e3dee38a8",
            albumartist="d'angelo",
            format="CD",
            album="the black messiah",
            title="Till It's Done (Tutu)",
        ),
        "expected": Item(
            artist="D'Angelo and the Vanguard",
            mb_albumid="ab140e13-7b36-402a-a528-b69e3dee38a8",
            albumartist="D'Angelo",
            format="CD",
            album="the black messiah",
            title="Till It's Done (Tutu)",
        ),
    }
]


class TitlecasePluginTest(PluginTestCase):
    plugin = "titlecase"
    preload_plugin = False

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

    def test_field_list(self):
        fields = ["album", "albumartist"]
        config["titlecase"]["fields"] = fields
        t = TitlecasePlugin()
        for field in fields:
            assert field in t.fields_to_process

    def test_field_list_default_excluded(self):
        excluded = list(EXCLUDED_INFO_FIELDS)
        config["titlecase"]["fields"] = excluded
        t = TitlecasePlugin()
        for field in excluded:
            assert field not in t.fields_to_process

    def test_preserved_words(self):
        """Test using given strings to preserve case"""
        names_to_preserve = [
            "easyFun",
            "A.D.O.R.",
            "D.R.",
            "D'Angelo",
            "ABBA",
            "LaTeX",
        ]
        config["titlecase"]["preserve"] = names_to_preserve
        for name in names_to_preserve:
            assert TitlecasePlugin().titlecase(name.lower()) == name
            assert TitlecasePlugin().titlecase(name.upper()) == name

    def test_preserved_phrases(self):
        phrases_to_preserve = ["The Beatles", "The Red Hed"]
        test_strings = ["Vinylgroover & The Red Hed", "With The Beatles"]
        config["titlecase"]["preserve"] = phrases_to_preserve
        t = TitlecasePlugin()
        for phrase in test_strings:
            assert t.titlecase(phrase.lower()) == phrase

    def test_titlecase_fields(self):
        for tc in titlecase_test_cases:
            item = tc["item"]
            expected = tc["expected"]
            config["titlecase"] = tc["config"]
            TitlecasePlugin().titlecase_fields(item)
            for key, value in vars(item).items():
                if isinstance(value, str):
                    assert getattr(item, key) == getattr(expected, key)

    def test_cli(self):
        for tc in titlecase_test_cases:
            with self.configure_plugin(tc["config"]):
                item = tc["item"]
                expected = tc["expected"]
                # Add item to library
                item.add(self.lib)
                self.run_command("titlecase")
                output = self.run_with_output("ls")
                assert (
                    output
                    == f"{expected.artist} - {expected.album} - {expected.title}\n"
                )
