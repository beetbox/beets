# This file is part of beets.
# Copyright 2024, Nicholas Boyd Isacsson.
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

"""Test the substitute plugin regex functionality."""

from beets.test.helper import PluginTestCase, capture_log
from beetsplug.substitute import Substitute


class SubstitutePluginTest(PluginTestCase):
    plugin = "substitute"
    preload_plugin = False

    def run_substitute(self, config, cases):
        with self.configure_plugin(config):
            for input, expected in cases:
                assert Substitute().tmpl_substitute(input) == expected

    def test_simple_substitute(self):
        self.run_substitute(
            [
                {"a": "b"},
                {"b": "c"},
                {"c": "d"},
            ],
            [("a", "b"), ("b", "c"), ("c", "d")],
        )

    def test_case_insensitivity(self):
        self.run_substitute([{"a": "b"}], [("A", "b")])

    def test_unmatched_input_preserved(self):
        self.run_substitute([{"a": "b"}], [("c", "c")])

    def test_regex_to_static(self):
        self.run_substitute(
            [{".*jimi hendrix.*": "Jimi Hendrix"}],
            [("The Jimi Hendrix Experience", "Jimi Hendrix")],
        )

    def test_regex_capture_group(self):
        self.run_substitute(
            [{"^(.*?)(,| &| and).*": r"\1"}],
            [
                ("King Creosote & Jon Hopkins", "King Creosote"),
                (
                    "Michael Hurley, The Holy Modal Rounders, Jeffrey Frederick & "
                    + "The Clamtones",
                    "Michael Hurley",
                ),
                ("James Yorkston and the Athletes", "James Yorkston"),
            ],
        )

    def test_partial_substitution(self):
        self.run_substitute([{r"\.": ""}], [("U.N.P.O.C.", "UNPOC")])

    def test_break_on_first_match(self):
        self.run_substitute(
            [
                {"a": "b"},
                {"[ab]": "c"},
            ],
            [
                ("a", "b"),
                ("b", "c"),
            ],
        )

    def test_deprecated_config(self):
        self.run_substitute(
            {
                "a": "b",
                "b": "c",
                "c": "d",
            },
            [("a", "b"), ("b", "c"), ("c", "d")],
        )

    def test_deprecated_config_warning(self):
        with capture_log() as logs:
            with self.configure_plugin(
                {
                    "a": "b",
                    "b": "c",
                    "c": "d",
                }
            ):
                assert any(
                    [
                        "Unordered configuration is deprecated, as it leads to"
                        + " unpredictable behaviour on overlapping rules"
                        in log
                        for log in logs
                    ]
                )
