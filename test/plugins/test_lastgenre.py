# This file is part of beets.
# Copyright 2016, Fabrice Laporte.
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

"""Tests for the 'lastgenre' plugin."""

from unittest.mock import Mock, patch

import pytest

from beets.test import _common
from beets.test.helper import PluginTestCase
from beetsplug import lastgenre


class LastGenrePluginTest(PluginTestCase):
    plugin = "lastgenre"

    def setUp(self):
        super().setUp()
        self.plugin = lastgenre.LastGenrePlugin()

    def _setup_config(
        self, whitelist=False, canonical=False, count=1, prefer_specific=False
    ):
        self.config["lastgenre"]["canonical"] = canonical
        self.config["lastgenre"]["count"] = count
        self.config["lastgenre"]["prefer_specific"] = prefer_specific
        if isinstance(whitelist, (bool, (str,))):
            # Filename, default, or disabled.
            self.config["lastgenre"]["whitelist"] = whitelist
        self.plugin.setup()
        if not isinstance(whitelist, (bool, (str,))):
            # Explicit list of genres.
            self.plugin.whitelist = whitelist

    def test_default(self):
        """Fetch genres with whitelist and c14n deactivated"""
        self._setup_config()
        assert self.plugin._resolve_genres(["delta blues"]) == ["delta blues"]

    def test_c14n_only(self):
        """Default c14n tree funnels up to most common genre except for *wrong*
        genres that stay unchanged.
        """
        self._setup_config(canonical=True, count=99)
        assert self.plugin._resolve_genres(["delta blues"]) == ["blues"]
        assert self.plugin._resolve_genres(["iota blues"]) == ["iota blues"]

    def test_whitelist_only(self):
        """Default whitelist rejects *wrong* (non existing) genres."""
        self._setup_config(whitelist=True)
        assert self.plugin._resolve_genres(["iota blues"]) == []

    def test_whitelist_c14n(self):
        """Default whitelist and c14n both activated result in all parents
        genres being selected (from specific to common).
        """
        self._setup_config(canonical=True, whitelist=True, count=99)
        assert self.plugin._resolve_genres(["delta blues"]) == [
            "delta blues",
            "blues",
        ]

    def test_whitelist_custom(self):
        """Keep only genres that are in the whitelist."""
        self._setup_config(whitelist={"blues", "rock", "jazz"}, count=2)
        assert self.plugin._resolve_genres(["pop", "blues"]) == ["blues"]

        self._setup_config(canonical="", whitelist={"rock"})
        assert self.plugin._resolve_genres(["delta blues"]) == []

    def test_format_genres(self):
        """Format genres list."""
        self._setup_config(count=2)
        assert self.plugin._format_genres(["jazz", "pop", "rock", "blues"]) == [
            "Jazz",
            "Pop",
            "Rock",
            "Blues",
        ]

    def test_count_c14n(self):
        """Keep the n first genres, after having applied c14n when necessary"""
        self._setup_config(
            whitelist={"blues", "rock", "jazz"}, canonical=True, count=2
        )
        # thanks to c14n, 'blues' superseeds 'country blues' and takes the
        # second slot
        assert self.plugin._resolve_genres(
            ["jazz", "pop", "country blues", "rock"]
        ) == ["jazz", "blues"]

    def test_c14n_whitelist(self):
        """Genres first pass through c14n and are then filtered"""
        self._setup_config(canonical=True, whitelist={"rock"})
        assert self.plugin._resolve_genres(["delta blues"]) == []

    def test_empty_string_enables_canonical(self):
        """For backwards compatibility, setting the `canonical` option
        to the empty string enables it using the default tree.
        """
        self._setup_config(canonical="", count=99)
        assert self.plugin._resolve_genres(["delta blues"]) == ["blues"]

    def test_empty_string_enables_whitelist(self):
        """Again for backwards compatibility, setting the `whitelist`
        option to the empty string enables the default set of genres.
        """
        self._setup_config(whitelist="")
        assert self.plugin._resolve_genres(["iota blues"]) == []

    def test_prefer_specific_loads_tree(self):
        """When prefer_specific is enabled but canonical is not the
        tree still has to be loaded.
        """
        self._setup_config(prefer_specific=True, canonical=False)
        assert self.plugin.c14n_branches != []

    def test_prefer_specific_without_canonical(self):
        """Prefer_specific works without canonical."""
        self._setup_config(prefer_specific=True, canonical=False, count=4)
        assert self.plugin._resolve_genres(["math rock", "post-rock"]) == [
            "post-rock",
            "math rock",
        ]

    @patch("beets.ui.should_write", Mock(return_value=True))
    @patch(
        "beetsplug.lastgenre.LastGenrePlugin._get_genre",
        Mock(return_value=("Mock Genre", "mock stage")),
    )
    def test_pretend_option_skips_library_updates(self):
        item = self.create_item(
            album="Pretend Album",
            albumartist="Pretend Artist",
            artist="Pretend Artist",
            title="Pretend Track",
            genre="Original Genre",
        )
        album = self.lib.add_album([item])

        def unexpected_store(*_, **__):
            raise AssertionError("Unexpected store call")

        # Verify that try_write was never called (file operations skipped)
        with patch("beetsplug.lastgenre.Item.store", unexpected_store):
            output = self.run_with_output("lastgenre", "--pretend")

        assert "genres:" in output
        album.load()
        assert album.genre == "Original Genre"
        assert album.items()[0].genre == "Original Genre"

    def test_no_duplicate(self):
        """Remove duplicated genres."""
        self._setup_config(count=99)
        assert self.plugin._resolve_genres(["blues", "blues"]) == ["blues"]

    def test_tags_for(self):
        class MockPylastElem:
            def __init__(self, name):
                self.name = name

            def get_name(self):
                return self.name

        class MockPylastObj:
            def get_top_tags(self):
                tag1 = Mock()
                tag1.weight = 90
                tag1.item = MockPylastElem("Pop")
                tag2 = Mock()
                tag2.weight = 40
                tag2.item = MockPylastElem("Rap")
                return [tag1, tag2]

        plugin = lastgenre.LastGenrePlugin()
        res = plugin._tags_for(MockPylastObj())
        assert res == ["pop", "rap"]
        res = plugin._tags_for(MockPylastObj(), min_weight=50)
        assert res == ["pop"]

    def test_sort_by_depth(self):
        self._setup_config(canonical=True)
        # Normal case.
        tags = ("electronic", "ambient", "post-rock", "downtempo")
        res = self.plugin._sort_by_depth(tags)
        assert res == ["post-rock", "downtempo", "ambient", "electronic"]
        # Non-canonical tag ('chillout') present.
        tags = ("electronic", "ambient", "chillout")
        res = self.plugin._sort_by_depth(tags)
        assert res == ["ambient", "electronic"]


@pytest.mark.parametrize(
    "config_values, item_genre, mock_genres, expected_result",
    [
        # 0 - force and keep whitelisted
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",  # means album or artist genre
                "whitelist": True,
                "canonical": False,
                "prefer_specific": False,
                "count": 10,
            },
            "Blues",
            {
                "album": ["Jazz"],
            },
            (["Blues", "Jazz"], "keep + album, whitelist"),
        ),
        # 1 - force and keep whitelisted, unknown original
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",
                "whitelist": True,
                "canonical": False,
                "prefer_specific": False,
            },
            "original unknown, Blues",
            {
                "album": ["Jazz"],
            },
            (["Blues", "Jazz"], "keep + album, whitelist"),
        ),
        # 2 - force and keep whitelisted on empty tag
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",
                "whitelist": True,
                "canonical": False,
                "prefer_specific": False,
            },
            "",
            {
                "album": ["Jazz"],
            },
            (["Jazz"], "album, whitelist"),
        ),
        # 3 force and keep, artist configured
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "artist",  # means artist genre, original or fallback
                "whitelist": True,
                "canonical": False,
                "prefer_specific": False,
            },
            "original unknown, Blues",
            {
                "album": ["Jazz"],
                "artist": ["Pop"],
            },
            (["Blues", "Pop"], "keep + artist, whitelist"),
        ),
        # 4 - don't force, disabled whitelist
        (
            {
                "force": False,
                "keep_existing": False,
                "source": "album",
                "whitelist": False,
                "canonical": False,
                "prefer_specific": False,
            },
            "any genre",
            {
                "album": ["Jazz"],
            },
            (["any genre"], "keep any, no-force"),
        ),
        # 5 - don't force and empty is regular last.fm fetch; no whitelist too
        (
            {
                "force": False,
                "keep_existing": False,
                "source": "album",
                "whitelist": False,
                "canonical": False,
                "prefer_specific": False,
            },
            "",
            {
                "album": ["Jazzin"],
            },
            (["Jazzin"], "album, any"),
        ),
        # 6 - fallback to next stages until found
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "track",  # means track,album,artist,...
                "whitelist": False,
                "canonical": False,
                "prefer_specific": False,
            },
            "unknown genre",
            {
                "track": None,
                "album": None,
                "artist": ["Jazz"],
            },
            (["Unknown Genre", "Jazz"], "keep + artist, any"),
        ),
        # 7 - Keep the original genre when force and keep_existing are on, and
        # whitelist is disabled
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "track",
                "whitelist": False,
                "fallback": "fallback genre",
                "canonical": False,
                "prefer_specific": False,
            },
            "any existing",
            {
                "track": None,
                "album": None,
                "artist": None,
            },
            (["any existing"], "original fallback"),
        ),
        # 7.1 - Keep the original genre when force and keep_existing are on, and
        # whitelist is enabled, and genre is valid.
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "track",
                "whitelist": True,
                "fallback": "fallback genre",
                "canonical": False,
                "prefer_specific": False,
            },
            "Jazz",
            {
                "track": None,
                "album": None,
                "artist": None,
            },
            (["Jazz"], "original fallback"),
        ),
        # 7.2 - Return the configured fallback when force is on but
        # keep_existing is not.
        (
            {
                "force": True,
                "keep_existing": False,
                "source": "track",
                "whitelist": True,
                "fallback": "fallback genre",
                "canonical": False,
                "prefer_specific": False,
            },
            "Jazz",
            {
                "track": None,
                "album": None,
                "artist": None,
            },
            (["fallback genre"], "fallback"),
        ),
        # 8 - fallback to fallback if no original
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "track",
                "whitelist": True,
                "fallback": "fallback genre",
                "canonical": False,
                "prefer_specific": False,
            },
            "",
            {
                "track": None,
                "album": None,
                "artist": None,
            },
            (["fallback genre"], "fallback"),
        ),
        # 9 - null charachter as separator
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",
                "whitelist": True,
                "separator": "\u0000",
                "canonical": False,
                "prefer_specific": False,
                "count": 10,
            },
            "Blues",
            {
                "album": ["Jazz"],
            },
            (["Blues", "Jazz"], "keep + album, whitelist"),
        ),
        # 10 - limit a lot of results
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",
                "whitelist": True,
                "count": 5,
                "canonical": False,
                "prefer_specific": False,
                "separator": ", ",
            },
            "original unknown, Blues, Rock, Folk, Metal",
            {
                "album": ["Jazz", "Bebop", "Hardbop"],
            },
            (
                ["Blues", "Rock", "Metal", "Jazz", "Bebop"],
                "keep + album, whitelist",
            ),
        ),
        # 11 - force off does not rely on configured separator
        (
            {
                "force": False,
                "keep_existing": False,
                "source": "album",
                "whitelist": True,
                "count": 2,
                "separator": ", ",
            },
            "not ; configured | separator",
            {
                "album": ["Jazz", "Bebop"],
            },
            (["not ; configured | separator"], "keep any, no-force"),
        ),
        # 12 - fallback to next stage (artist) if no allowed original present
        # and no album genre were fetched.
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",
                "whitelist": True,
                "fallback": "fallback genre",
                "canonical": False,
                "prefer_specific": False,
            },
            "not whitelisted original",
            {
                "track": None,
                "album": None,
                "artist": ["Jazz"],
            },
            (["Jazz"], "keep + artist, whitelist"),
        ),
        # 13 - canonicalization transforms non-whitelisted genres to canonical forms
        #
        # "Acid Techno" is not in the default whitelist, thus gets resolved "up" in the
        # tree to "Techno" and "Electronic".
        (
            {
                "force": True,
                "keep_existing": False,
                "source": "album",
                "whitelist": True,
                "canonical": True,
                "prefer_specific": False,
                "count": 10,
            },
            "",
            {
                "album": ["acid techno"],
            },
            (["Techno", "Electronic"], "album, whitelist"),
        ),
        # 14 - canonicalization transforms whitelisted genres to canonical forms and
        # includes originals
        #
        # "Detroit Techno" is in the default whitelist, thus it stays and and also gets
        # resolved "up" in the tree to "Techno" and "Electronic". The same happens for
        # newly fetched genre "Acid House".
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",
                "whitelist": True,
                "canonical": True,
                "prefer_specific": False,
                "count": 10,
                "extended_debug": True,
            },
            "detroit techno",
            {
                "album": ["acid house"],
            },
            (
                [
                    "Detroit Techno",
                    "Techno",
                    "Electronic",
                    "Acid House",
                    "House",
                ],
                "keep + album, whitelist",
            ),
        ),
        # 15 - canonicalization transforms non-whitelisted original genres to canonical
        # forms and deduplication works.
        #
        # "Cosmic Disco" is not in the default whitelist, thus gets resolved "up" in the
        # tree to "Disco" and "Electronic". New genre "Detroit Techno" resolves to
        # "Techno". Both resolve to "Electronic" which gets deduplicated.
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",
                "whitelist": True,
                "canonical": True,
                "prefer_specific": False,
                "count": 10,
            },
            "Cosmic Disco",
            {
                "album": ["Detroit Techno"],
            },
            (
                ["Disco", "Electronic", "Detroit Techno", "Techno"],
                "keep + album, whitelist",
            ),
        ),
    ],
)
def test_get_genre(config_values, item_genre, mock_genres, expected_result):
    """Test _get_genre with various configurations."""

    def mock_fetch_track_genre(self, obj=None):
        return mock_genres["track"]

    def mock_fetch_album_genre(self, obj):
        return mock_genres["album"]

    def mock_fetch_artist_genre(self, obj):
        return mock_genres["artist"]

    # Mock the last.fm fetchers. When whitelist enabled, we can assume only
    # whitelisted genres get returned, the plugin's _resolve_genre method
    # ensures it.
    lastgenre.LastGenrePlugin.fetch_track_genre = mock_fetch_track_genre
    lastgenre.LastGenrePlugin.fetch_album_genre = mock_fetch_album_genre
    lastgenre.LastGenrePlugin.fetch_artist_genre = mock_fetch_artist_genre

    # Initialize plugin instance and item
    plugin = lastgenre.LastGenrePlugin()
    # Configure
    plugin.config.set(config_values)
    plugin.setup()  # Loads default whitelist and canonicalization tree

    item = _common.item()
    # Set genres as a list - if item_genre is a string, convert it to list
    if item_genre:
        # For compatibility with old separator-based tests, split if needed
        if (
            "separator" in config_values
            and config_values["separator"] in item_genre
        ):
            sep = config_values["separator"]
            item.genres = [
                g.strip() for g in item_genre.split(sep) if g.strip()
            ]
        else:
            # Assume comma-separated if no specific separator
            if ", " in item_genre:
                item.genres = [
                    g.strip() for g in item_genre.split(", ") if g.strip()
                ]
            else:
                item.genres = [item_genre]
    else:
        item.genres = []

    # Run
    res = plugin._get_genre(item)
    expected_genres, expected_label = expected_result
    assert res == (expected_genres, expected_label)
