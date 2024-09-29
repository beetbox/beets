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

import pytest

from beets.test.helper import PluginTestCase
from beetsplug.substitute import Substitute

PLUGIN_NAME = "substitute"

class SubstitutePluginTest(PluginTestCase):
    plugin = "substitute"
    preload_plugin = False

    def test_simple_substitute(self):
        with self.configure_plugin(
            {
                "a": "b",
                "b": "c",
                "c": "d",
            }
        ):
            cases = [
                ("a", "b"),
                ("b", "c"),
                ("c", "d")
            ]
            for input, expected in cases:
                assert Substitute().tmpl_substitute(input) == expected

    def test_case_insensitivity(self):
        with self.configure_plugin(
            { "a": "b" }
        ):
            assert Substitute().tmpl_substitute("A") == "b"

    def test_unmatched_input_preserved(self):
        with self.configure_plugin(
            { "a": "b" }
        ):
            assert Substitute().tmpl_substitute("c") == "c"

    def test_regex_to_static(self):
        with self.configure_plugin(
            { ".*jimi hendrix.*": "Jimi Hendrix" }
        ):
            assert Substitute().tmpl_substitute("The Jimi Hendrix Experience") == "Jimi Hendrix"

    def test_regex_capture_group(self):
        with self.configure_plugin(
            { "^(.*?)(,| &| and).*": r"\1" }
        ):
            cases = [
                ("King Creosote & Jon Hopkins", "King Creosote"),
                ("Michael Hurley, The Holy Modal Rounders, Jeffrey Frederick & The Clamtones", "Michael Hurley"),
                ("James Yorkston and the Athletes", "James Yorkston")
            ]
            for case in cases:
                assert Substitute().tmpl_substitute(case[0]) == case[1]

    def test_partial_substitution(self):
        with self.configure_plugin(
            {
                r"\.": "",
            }
        ):
            cases = [
                ("U.N.P.O.C.", "UNPOC"),
            ]
            for input, expected in cases:
                assert Substitute().tmpl_substitute(input) == expected


    def test_break_on_first_match(self):
        with self.configure_plugin(
            {
                "a": "b",
                "[ab]": "c",
            }
        ):
            cases = [
                ("a", "b"),
                ("b", "c"),
            ]
            for case in cases:
                assert Substitute().tmpl_substitute(case[0]) == case[1]
