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

import os
import re
import tempfile
from collections import defaultdict
from unittest.mock import Mock

import pytest

from beets.test import _common
from beets.test.helper import BeetsTestCase
from beets.ui import UserError
from beetsplug import lastgenre


class LastGenrePluginTest(BeetsTestCase):
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

    def test_format_and_stringify(self):
        """Format genres list and return them as a separator-delimited string."""
        self._setup_config(count=2)
        assert (
            self.plugin._format_and_stringify(["jazz", "pop", "rock", "blues"])
            == "Jazz, Pop, Rock, Blues"
        )

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
            ("Blues, Jazz", "keep + album, whitelist"),
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
            ("Blues, Jazz", "keep + album, whitelist"),
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
            ("Jazz", "album, whitelist"),
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
            ("Blues, Pop", "keep + artist, whitelist"),
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
            ("any genre", "keep any, no-force"),
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
            ("Jazzin", "album, any"),
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
            ("Unknown Genre, Jazz", "keep + artist, any"),
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
            ("any existing", "original fallback"),
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
            ("Jazz", "original fallback"),
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
            ("fallback genre", "fallback"),
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
            ("fallback genre", "fallback"),
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
            },
            "Blues",
            {
                "album": ["Jazz"],
            },
            ("Blues\u0000Jazz", "keep + album, whitelist"),
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
            ("Blues, Rock, Metal, Jazz, Bebop", "keep + album, whitelist"),
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
            ("not ; configured | separator", "keep any, no-force"),
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
            ("Jazz", "keep + artist, whitelist"),
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
            ("Techno, Electronic", "album, whitelist"),
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
                "Detroit Techno, Techno, Electronic, Acid House, House",
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
                "Disco, Electronic, Detroit Techno, Techno",
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
    item.genre = item_genre

    # Run
    res = plugin._get_genre(item)
    assert res == expected_result


@pytest.mark.parametrize(
    "blacklist_dict, artist, genre, expected_forbidden",
    [
        # Global blacklist - simple word
        ({"*": ["spoken word"]}, "Any Artist", "spoken word", True),
        ({"*": ["spoken word"]}, "Any Artist", "jazz", False),
        # Global blacklist - regex pattern
        ({"*": [".*electronic.*"]}, "Any Artist", "ambient electronic", True),
        ({"*": [".*electronic.*"]}, "Any Artist", "jazz", False),
        # Artist-specific blacklist
        ({"metallica": ["metal"]}, "Metallica", "metal", True),
        ({"metallica": ["metal"]}, "Iron Maiden", "metal", False),
        # Case insensitive matching
        ({"metallica": ["metal"]}, "METALLICA", "METAL", True),
        # Artist-specific blacklist - exact match
        ({"metallica": ["^Heavy Metal$"]}, "Metallica", "classic metal", False),
        # Combined global and artist-specific
        (
            {"*": ["spoken word"], "metallica": ["metal"]},
            "Metallica",
            "spoken word",
            True,
        ),
        (
            {"*": ["spoken word"], "metallica": ["metal"]},
            "Metallica",
            "metal",
            True,
        ),
        # Complex regex pattern with multiple features (raw string)
        (
            {
                "fracture": [
                    r"^(heavy|black|power|death)?\s?(metal|rock)$|\w+-metal\d*$"
                ]
            },
            "Fracture",
            "power metal",
            True,
        ),
        # Complex regex pattern with multiple features (regular string)
        (
            {"amon tobin": ["d(rum)?[ n/]*b(ass)?"]},
            "Amon Tobin",
            "dnb",
            True,
        ),
        # Empty blacklist
        ({}, "Any Artist", "any genre", False),
    ],
)
def test_blacklist_patterns(blacklist_dict, artist, genre, expected_forbidden):
    """Test blacklist pattern matching logic directly."""

    # Initialize plugin
    plugin = lastgenre.LastGenrePlugin()

    # Set up compiled blacklist directly (skipping file parsing)
    compiled_blacklist = defaultdict(list)
    for artist_name, patterns in blacklist_dict.items():
        compiled_blacklist[artist_name.lower()] = [
            re.compile(pattern) for pattern in patterns
        ]

    plugin.blacklist = compiled_blacklist

    # Test the _is_forbidden method
    result = plugin._is_forbidden(genre, artist)
    assert result == expected_forbidden


@pytest.mark.parametrize(
    "file_content, expected_blacklist",
    [
        # Basic artist with pattern
        ("metallica:\n    metal", {"metallica": ["metal"]}),
        # Global blacklist
        ("*:\n    spoken word", {"*": ["spoken word"]}),
        # Multiple patterns per artist
        (
            "metallica:\n    metal\n    .*rock.*",
            {"metallica": ["metal", ".*rock.*"]},
        ),
        # Comments and empty lines ignored
        (
            "# comment\n*:\n    spoken word\n\nmetallica:\n    metal",
            {"*": ["spoken word"], "metallica": ["metal"]},
        ),
        # Case insensitive artist names
        ("METALLICA:\n    METAL", {"metallica": ["metal"]}),
        # Invalid regex pattern that gets escaped
        ("artist:\n    [invalid(regex", {"artist": ["\\[invalid\\(regex"]}),
        # Empty file
        ("", {}),
    ],
)
def test_blacklist_file_format(file_content, expected_blacklist):
    """Test blacklist file format parsing."""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(file_content)
        blacklist_file = f.name

    try:
        plugin = lastgenre.LastGenrePlugin()
        plugin.config["blacklist"] = blacklist_file
        blacklist_result = plugin._load_blacklist()

        # Convert compiled regex patterns back to strings for comparison
        string_blacklist = {}
        for artist, compiled_patterns in blacklist_result.items():
            string_blacklist[artist] = [
                pattern.pattern for pattern in compiled_patterns
            ]

        assert string_blacklist == expected_blacklist

    finally:
        os.unlink(blacklist_file)


@pytest.mark.parametrize(
    "invalid_content, expected_error_message",
    [
        # Missing colon
        ("metallica\n    metal", "Malformed blacklist section header"),
        # Pattern before section
        ("    metal\nmetallica:\n    heavy metal", "before any section header"),
        # Unindented pattern
        ("metallica:\nmetal", "Malformed blacklist section header"),
    ],
)
def test_blacklist_file_format_errors(invalid_content, expected_error_message):
    """Test blacklist file format error handling."""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(invalid_content)
        blacklist_file = f.name

    try:
        plugin = lastgenre.LastGenrePlugin()
        plugin.config["blacklist"] = blacklist_file

        with pytest.raises(UserError) as exc_info:
            plugin._load_blacklist()

        assert expected_error_message in str(exc_info.value)

    finally:
        os.unlink(blacklist_file)
