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

from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.library import Item
from beets.test.helper import PluginMixin
from beetsplug.titlecase import TitlecasePlugin


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


to_preserve = [
    "easyFun",
    "A.D.O.R",
    "D'Angelo",
    "ABBA",
    "LaTeX",
    "O.R.B",
    "PinkPantheress",
]


@pytest.mark.parametrize("name", to_preserve)
def test_preserved_words(name):
    """Test using given strings to preserve case"""
    t = TitlecasePlugin()
    t._preserve_words(to_preserve)
    assert t.titlecase(name.lower()) == name
    assert t.titlecase(name.upper()) == name


def phrases_with_preserved_strings(phrases: list[str]) -> list[tuple[str, str]]:
    def template(x):
        return f"Example Phrase: Or {x} in Context!"

    return [(template(p.lower()), template(p)) for p in phrases]


@pytest.mark.parametrize(
    "given, expected", phrases_with_preserved_strings(to_preserve)
)
def test_preserved_phrases(given, expected):
    t = TitlecasePlugin()
    t._preserve_words(to_preserve)
    assert t.titlecase(given.lower()) == expected


item_test_cases = [
    (
        {
            "preserve": ["D'Angelo"],
            "replace": [("’", "'")],
            "fields": ["artist", "albumartist", "mb_albumid"],
            "force_lowercase": False,
            "small_first_last": True,
        },
        Item(
            artist="d’angelo and the vanguard",
            mb_albumid="ab140e13-7b36-402a-a528-b69e3dee38a8",
            albumartist="d’angelo",
            format="CD",
            album="the black messiah",
            title="Till It's Done (Tutu)",
        ),
        Item(
            artist="D'Angelo and The Vanguard",
            mb_albumid="Ab140e13-7b36-402a-A528-B69e3dee38a8",
            albumartist="D'Angelo",
            format="CD",
            album="the black messiah",
            title="Till It's Done (Tutu)",
        ),
    ),
    (
        {
            "fields": [
                "artist",
                "albumartist",
                "title",
                "album",
                "mb_albumd",
                "year",
            ],
            "force_lowercase": True,
            "small_first_last": True,
        },
        Item(
            artist="OPHIDIAN",
            albumartist="ophiDIAN",
            format="CD",
            year=2003,
            album="BLACKBOX",
            title="KhAmElEoN",
        ),
        Item(
            artist="Ophidian",
            albumartist="Ophidian",
            format="CD",
            year=2003,
            album="Blackbox",
            title="Khameleon",
        ),
    ),
    (
        {
            "the_artist": True,
            "preserve": ["PANTHER"],
            "fields": ["artist", "artists", "discogs_artistid"],
            "force_lowercase": False,
            "small_first_last": True,
        },
        Item(
            artist="pinkpantheress",
            artists=["pinkpantheress", "artist_two"],
            artists_ids=["aBcDeF32", "aBcDeF12"],
            discogs_artistid=21,
        ),
        Item(
            artist="Pinkpantheress",
            artists=["Pinkpantheress", "Artist_Two"],
            artists_ids=["aBcDeF32", "aBcDeF12"],
            discogs_artistid=21,
        ),
    ),
    (
        {
            "the_artist": True,
            "preserve": ["A Day in the Park"],
            "fields": [
                "artists",
                "artist",
                "artists_sorttitle",
                "artists_ids",
            ],
        },
        Item(
            artists_sort=["b-52s, the"],
            artist="a day in the park",
            artists=[
                "vinylgroover & the red head",
                "a day in the park",
                "amyl and the sniffers",
            ],
            artists_ids=["aBcDeF32", "aBcDeF12"],
        ),
        Item(
            artists_sort=["B-52s, The"],
            artist="A Day in the Park",
            artists=[
                "Vinylgroover & The Red Head",
                "A Day in The Park",
                "Amyl and The Sniffers",
            ],
            artists_ids=["ABcDeF32", "ABcDeF12"],
        ),
    ),
    (
        {
            "the_artist": False,
            "preserve": ["A Day in the Park"],
            "fields": [
                "artists",
                "artist",
                "artists_sorttitle",
                "artists_ids",
            ],
        },
        Item(
            artists_sort=["b-52s, the"],
            artist="a day in the park",
            artists=[
                "vinylgroover & the red head",
                "a day in the park",
                "amyl and the sniffers",
            ],
            artists_ids=["aBcDeF32", "aBcDeF12"],
        ),
        Item(
            artists_sort=["B-52s, The"],
            artist="A Day in the Park",
            artists=[
                "Vinylgroover & the Red Head",
                "A Day in the Park",
                "Amyl and the Sniffers",
            ],
            artists_ids=["ABcDeF32", "ABcDeF12"],
        ),
    ),
]

info_test_cases = [
    (
        TrackInfo(
            album="test album",
            artist_credit="test artist credit",
            artists=["artist one", "artist two"],
        ),
        TrackInfo(
            album="Test Album",
            artist_credit="Test Artist Credit",
            artists=["Artist One", "Artist Two"],
        ),
    ),
    (
        AlbumInfo(
            tracks=[
                TrackInfo(
                    album="test album",
                    artist_credit="test artist credit",
                    artists=["artist one", "artist two"],
                )
            ],
            album="test album",
            artist_credit="test artist credit",
            artists=["artist one", "artist two"],
        ),
        AlbumInfo(
            tracks=[
                TrackInfo(
                    album="Test Album",
                    artist_credit="Test Artist Credit",
                    artists=["Artist One", "Artist Two"],
                )
            ],
            album="Test Album",
            artist_credit="Test Artist Credit",
            artists=["Artist One", "Artist Two"],
        ),
    ),
]


class TitlecasePluginMethodTests(PluginMixin):
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
        with self.configure_plugin({"fields": fields}):
            t = TitlecasePlugin()
            for field in fields:
                assert field in t.fields_to_process

    @pytest.mark.parametrize("given, expected", info_test_cases)
    def test_received_info_handler(self, given, expected):
        with self.configure_plugin(
            {"fields": ["album", "artist_credit", "artists"]}
        ):
            TitlecasePlugin().received_info_handler(given)
            assert given == expected


@pytest.mark.parametrize("config, given, expected", item_test_cases)
class TitlecasePluginTest(PluginMixin):
    plugin = "titlecase"
    preload_plugin = False

    def test_titlecase_fields(self, config, given, expected):
        with self.configure_plugin(config):
            TitlecasePlugin.titlecase_fields(given)
            assert given == expected

    def test_cli(self, config, given, expected):
        with self.configure_plugin(config):
            given.add(self.lib)
            self.run_command("titlecase")
            output = self.run_with_output("ls")
            assert (
                output
                == f"{expected.artist} - {expected.album} - {expected.title}\n"
            )
            self.run_command("remove", expected.artist, "-f")
