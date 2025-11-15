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
from beets.test.helper import PluginTestCase
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


titlecase_test_cases = [
    {
        "config": {
            "preserve": ["D'Angelo"],
            "replace": [("’", "'")],
            "fields": ["artist", "albumartist", "mb_albumid"],
            "force_lowercase": False,
            "small_first_last": True,
        },
        "item": Item(
            artist="d’angelo and the vanguard",
            mb_albumid="ab140e13-7b36-402a-a528-b69e3dee38a8",
            albumartist="d’angelo",
            format="CD",
            album="the black messiah",
            title="Till It's Done (Tutu)",
        ),
        "expected": Item(
            artist="D'Angelo and The Vanguard",
            mb_albumid="Ab140e13-7b36-402a-A528-B69e3dee38a8",
            albumartist="D'Angelo",
            format="CD",
            album="the black messiah",
            title="Till It's Done (Tutu)",
        ),
    },
    {
        "config": {
            "preserve": [""],
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
        "item": Item(
            artist="OPHIDIAN",
            albumartist="ophiDIAN",
            format="CD",
            year=2003,
            album="BLACKBOX",
            title="KhAmElEoN",
        ),
        "expected": Item(
            artist="Ophidian",
            albumartist="Ophidian",
            format="CD",
            year=2003,
            album="Blackbox",
            title="Khameleon",
        ),
    },
    {
        "config": {
            "preserve": [""],
            "fields": ["artists", "discogs_artistid"],
            "force_lowercase": False,
            "small_first_last": True,
        },
        "item": Item(
            artists=["artist_one", "artist_two"],
            artists_ids=["aBcDeF32", "aBcDeF12"],
            discogs_artistid=21,
        ),
        "expected": Item(
            artists=["Artist_One", "Artist_Two"],
            artists_ids=["aBcDeF32", "aBcDeF12"],
            discogs_artistid=21,
        ),
    },
    {
        "config": {
            "the_artist": True,
            "preserve": ["A Day in the Park"],
            "fields": [
                "artists",
                "artist",
                "artists_sorttitle",
                "artists_ids",
            ],
        },
        "item": Item(
            artists_sort=["b-52s, the"],
            artist="a day in the park",
            artists=[
                "vinylgroover & the red head",
                "a day in the park",
                "amyl and the sniffers",
            ],
            artists_ids=["aBcDeF32", "aBcDeF12"],
        ),
        "expected": Item(
            artists_sort=["B-52s, The"],
            artist="A Day in the Park",
            artists=[
                "Vinylgroover & The Red Head",
                "A Day in The ParkAmyl and The Sniffers",
            ],
            artists_ids=["ABcDeF32", "ABcDeF12"],
        ),
    },
    {
        "config": {
            "the_artist": False,
            "preserve": ["A Day in the Park"],
            "fields": [
                "artists",
                "artist",
                "artists_sorttitle",
                "artists_ids",
            ],
        },
        "item": Item(
            artists_sort=["b-52s, the"],
            artist="a day in the park",
            artists=[
                "vinylgroover & the red head",
                "a day in the park",
                "amyl and the sniffers",
            ],
            artists_ids=["aBcDeF32", "aBcDeF12"],
        ),
        "expected": Item(
            artists_sort=["B-52s, The"],
            artist="A Day in the Park",
            artists=[
                "Vinylgroover & the Red Head",
                "A Day in the ParkAmyl and the Sniffers",
            ],
            artists_ids=["ABcDeF32", "ABcDeF12"],
        ),
    },
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
        with self.configure_plugin({"fields": fields}):
            t = TitlecasePlugin()
            for field in fields:
                assert field in t.fields_to_process

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
        with self.configure_plugin({"preserve": names_to_preserve}):
            for name in names_to_preserve:
                assert TitlecasePlugin().titlecase(name.lower()) == name
                assert TitlecasePlugin().titlecase(name.upper()) == name

    def test_preserved_phrases(self):
        test_strings = ["Vinylgroover & The Red Hed", "With The Beatles"]
        phrases_to_preserve = ["The Beatles", "The Red Hed"]
        with self.configure_plugin({"preserve": phrases_to_preserve}):
            t = TitlecasePlugin()
            for phrase in test_strings:
                assert t.titlecase(phrase.lower()) == phrase

    def test_titlecase_fields(self):
        for tc in titlecase_test_cases:
            with self.configure_plugin(tc["config"]):
                item = tc["item"]
                expected = tc["expected"]
                TitlecasePlugin().titlecase_fields(item)
                for key, value in vars(item).items():
                    if isinstance(value, str):
                        assert getattr(item, key) == getattr(expected, key)

    def test_recieved_info_handler(self):
        test_track_info = TrackInfo(
            album="test album",
            artist_credit="test artist credit",
            artists=["artist one", "artist two"],
        )
        expected_track_info = TrackInfo(
            album="Test Album",
            artist_credit="Test Artist Credit",
            artists=["Artist One", "Artist Two"],
        )
        test_album_info = AlbumInfo(
            tracks=[test_track_info],
            album="test album",
            artist_credit="test artist credit",
            artists=["artist one", "artist two"],
        )
        expected_album_info = AlbumInfo(
            tracks=[expected_track_info],
            album="Test Album",
            artist_credit="Test Artist Credit",
            artists=["Artist One", "Artist Two"],
        )
        with self.configure_plugin(
            {"fields": ["album", "artist_credit", "artists"]}
        ):
            TitlecasePlugin().received_info_handler(test_track_info)
            assert test_track_info.album == expected_track_info.album
            assert (
                test_track_info.artist_credit
                == expected_track_info.artist_credit
            )
            assert test_track_info.artists == expected_track_info.artists
            TitlecasePlugin().received_info_handler(test_album_info)
            assert test_album_info.album == expected_album_info.album
            assert (
                test_album_info.artist_credit
                == expected_album_info.artist_credit
            )
            assert test_album_info.artists == expected_album_info.artists

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
                self.run_command("remove", expected.artist, "-f")
