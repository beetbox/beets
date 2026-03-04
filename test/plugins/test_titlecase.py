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

from unittest.mock import patch

from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.importer import ImportSession, ImportTask
from beets.library import Item
from beets.test.helper import PluginTestCase
from beetsplug.titlecase import TitlecasePlugin

titlecase_fields_testcases = [
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
]


class TestTitlecasePlugin(PluginTestCase):
    plugin = "titlecase"
    preload_plugin = False

    def test_auto(self):
        """Ensure automatic processing gets assigned"""
        with self.configure_plugin({"auto": True, "after_choice": True}):
            assert callable(TitlecasePlugin().import_stages[0])
        with self.configure_plugin({"auto": False, "after_choice": False}):
            assert len(TitlecasePlugin().import_stages) == 0
        with self.configure_plugin({"auto": False, "after_choice": True}):
            assert len(TitlecasePlugin().import_stages) == 0

    def test_basic_titlecase(self):
        """Check that default behavior is as expected."""
        testcases = [
            ("a", "A"),
            ("PENDULUM", "Pendulum"),
            ("Aaron-carl", "Aaron-Carl"),
            ("LTJ bukem", "LTJ Bukem"),
            ("(original mix)", "(Original Mix)"),
            ("ALL CAPS TITLE", "All Caps Title"),
        ]
        for testcase in testcases:
            given, expected = testcase
            assert TitlecasePlugin().titlecase(given) == expected

    def test_small_first_last(self):
        """Check the behavior for supporting small first last"""
        testcases = [
            (True, "In a Silent Way", "In a Silent Way"),
            (False, "In a Silent Way", "in a Silent Way"),
        ]
        for testcase in testcases:
            sfl, given, expected = testcase
            cfg = {"small_first_last": sfl}
            with self.configure_plugin(cfg):
                assert TitlecasePlugin().titlecase(given) == expected

    def test_preserve(self):
        """Test using given strings to preserve case"""
        preserve_list = [
            "easyFun",
            "A.D.O.R",
            "D'Angelo",
            "ABBA",
            "LaTeX",
            "O.R.B",
            "PinkPantheress",
            "THE PSYCHIC ED RUSH",
            "LTJ Bukem",
        ]
        for word in preserve_list:
            with self.configure_plugin({"preserve": preserve_list}):
                assert TitlecasePlugin().titlecase(word.upper()) == word
                assert TitlecasePlugin().titlecase(word.lower()) == word

    def test_separators(self):
        testcases = [
            ([], "it / a / in / of / to / the", "It / a / in / of / to / The"),
            (["/"], "it / the test", "It / The Test"),
            (
                ["/"],
                "it / a / in / of / to / the",
                "It / A / In / Of / To / The",
            ),
            (["/"], "//it/a/in/of/to/the", "//It/A/In/Of/To/The"),
            (
                ["/", ";", "|"],
                "it ; a / in | of / to | the",
                "It ; A / In | Of / To | The",
            ),
        ]
        for testcase in testcases:
            separators, given, expected = testcase
            with self.configure_plugin({"separators": separators}):
                assert TitlecasePlugin().titlecase(given) == expected

    def test_all_caps(self):
        testcases = [
            (True, "Unaffected", "Unaffected"),
            (True, "RBMK1000", "RBMK1000"),
            (False, "RBMK1000", "Rbmk1000"),
            (True, "P A R I S!", "P A R I S!"),
            (True, "pillow dub...", "Pillow Dub..."),
            (False, "P A R I S!", "P a R I S!"),
        ]
        for testcase in testcases:
            all_caps, given, expected = testcase
            with self.configure_plugin({"all_caps": all_caps}):
                assert TitlecasePlugin().titlecase(given) == expected

    def test_all_lowercase(self):
        testcases = [
            (True, "Unaffected", "Unaffected"),
            (True, "RBMK1000", "Rbmk1000"),
            (True, "pillow dub...", "pillow dub..."),
            (False, "pillow dub...", "Pillow Dub..."),
        ]
        for testcase in testcases:
            all_lowercase, given, expected = testcase
            with self.configure_plugin({"all_lowercase": all_lowercase}):
                assert TitlecasePlugin().titlecase(given) == expected

    def test_received_info_handler(self):
        testcases = [
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
        cfg = {"fields": ["album", "artist_credit", "artists"]}
        for testcase in testcases:
            given, expected = testcase
            with self.configure_plugin(cfg):
                TitlecasePlugin().received_info_handler(given)
                assert given == expected

    def test_titlecase_fields(self):
        testcases = [
            # Test with preserve, replace, and mb_albumid
            # Test with the_artist
            (
                {
                    "preserve": ["D'Angelo"],
                    "replace": [("’", "'")],
                    "fields": ["artist", "albumartist", "mb_albumid"],
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
            # Test with force_lowercase, preserve, and an incorrect field
            (
                {
                    "force_lowercase": True,
                    "fields": [
                        "artist",
                        "albumartist",
                        "format",
                        "title",
                        "year",
                        "label",
                        "format",
                        "INCORRECT_FIELD",
                    ],
                    "preserve": ["CD"],
                },
                Item(
                    artist="OPHIDIAN",
                    albumartist="OphiDIAN",
                    format="cd",
                    year=2003,
                    album="BLACKBOX",
                    title="KhAmElEoN",
                    label="enzyme records",
                ),
                Item(
                    artist="Ophidian",
                    albumartist="Ophidian",
                    format="CD",
                    year=2003,
                    album="Blackbox",
                    title="Khameleon",
                    label="Enzyme Records",
                ),
            ),
            # Test with no changes
            (
                {
                    "fields": [
                        "artist",
                        "artists",
                        "albumartist",
                        "format",
                        "title",
                        "year",
                        "label",
                        "format",
                        "INCORRECT_FIELD",
                    ],
                    "preserve": ["CD"],
                },
                Item(
                    artist="Ophidian",
                    artists=["Ophidian"],
                    albumartist="Ophidian",
                    format="CD",
                    year=2003,
                    album="Blackbox",
                    title="Khameleon",
                    label="Enzyme Records",
                ),
                Item(
                    artist="Ophidian",
                    artists=["Ophidian"],
                    albumartist="Ophidian",
                    format="CD",
                    year=2003,
                    album="Blackbox",
                    title="Khameleon",
                    label="Enzyme Records",
                ),
            ),
            # Test with the_artist disabled
            (
                {
                    "the_artist": False,
                    "fields": [
                        "artist",
                        "artists_sort",
                    ],
                },
                Item(
                    artists_sort=["b-52s, the"],
                    artist="a day in the park",
                ),
                Item(
                    artists_sort=["B-52s, The"],
                    artist="A Day in the Park",
                ),
            ),
            # Test to make sure preserve and the_artist
            # dont target the middle of sentences
            # show that The artist applies to any field
            # with artist mentioned
            (
                {
                    "preserve": ["PANTHER"],
                    "fields": ["artist", "artists", "artists_ids"],
                },
                Item(
                    artist="pinkpantheress",
                    artists=["pinkpantheress", "artist_two"],
                    artists_ids=["the the", "the the"],
                ),
                Item(
                    artist="Pinkpantheress",
                    artists=["Pinkpantheress", "Artist_two"],
                    artists_ids=["The The", "The The"],
                ),
            ),
        ]
        for testcase in testcases:
            cfg, given, expected = testcase
            with self.configure_plugin(cfg):
                TitlecasePlugin().titlecase_fields(given)
                assert given.artist == expected.artist
                assert given.artists == expected.artists
                assert given.artists_sort == expected.artists_sort
                assert given.albumartist == expected.albumartist
                assert given.artists_ids == expected.artists_ids
                assert given.format == expected.format
                assert given.year == expected.year
                assert given.title == expected.title
                assert given.label == expected.label

    def test_cli_write(self):
        given = Item(
            album="retrodelica 2: back 2 the future",
            artist="blue planet corporation",
            title="generator",
        )
        expected = Item(
            album="Retrodelica 2: Back 2 the Future",
            artist="Blue Planet Corporation",
            title="Generator",
        )
        cfg = {"fields": ["album", "artist", "title"]}
        with self.configure_plugin(cfg):
            given.add(self.lib)
            self.run_command("titlecase")
            assert self.lib.items().get().artist == expected.artist
            assert self.lib.items().get().album == expected.album
            assert self.lib.items().get().title == expected.title
            self.lib.items().get().remove()

    def test_cli_no_write(self):
        given = Item(
            album="retrodelica 2: back 2 the future",
            artist="blue planet corporation",
            title="generator",
        )
        expected = Item(
            album="retrodelica 2: back 2 the future",
            artist="blue planet corporation",
            title="generator",
        )
        cfg = {"fields": ["album", "artist", "title"]}
        with self.configure_plugin(cfg):
            given.add(self.lib)
            self.run_command("-p", "titlecase")
            assert self.lib.items().get().artist == expected.artist
            assert self.lib.items().get().album == expected.album
            assert self.lib.items().get().title == expected.title
            self.lib.items().get().remove()

    def test_imported(self):
        given = Item(
            album="retrodelica 2: back 2 the future",
            artist="blue planet corporation",
            title="generator",
        )
        expected = Item(
            album="Retrodelica 2: Back 2 the Future",
            artist="Blue Planet Corporation",
            title="Generator",
        )
        p = patch("beets.importer.ImportTask.imported_items", lambda x: [given])
        p.start()
        with self.configure_plugin({"fields": ["album", "artist", "title"]}):
            import_session = ImportSession(
                self.lib, loghandler=None, paths=None, query=None
            )
            import_task = ImportTask(toppath=None, paths=None, items=[given])
            TitlecasePlugin().imported(import_session, import_task)
            import_task.add(self.lib)
            item = self.lib.items().get()
            assert item.artist == expected.artist
            assert item.album == expected.album
            assert item.title == expected.title
        p.stop()
