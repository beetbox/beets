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

import re
from collections import defaultdict
from unittest.mock import MagicMock, Mock, patch

import pytest

from beets.library import Album
from beets.test import _common
from beets.test.helper import IOMixin, PluginTestCase
from beets.ui import UserError
from beetsplug import lastgenre
from beetsplug.lastgenre.utils import is_ignored


class LastGenrePluginTest(IOMixin, PluginTestCase):
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
            genres=["Original Genre"],
        )
        album = self.lib.add_album([item])

        def unexpected_store(*_, **__):
            raise AssertionError("Unexpected store call")

        # Verify that try_write was never called (file operations skipped)
        with patch("beetsplug.lastgenre.Item.store", unexpected_store):
            output = self.run_with_output("lastgenre", "--pretend")

        assert "genres:" in output
        album.load()
        assert album.genres == ["Original Genre"]
        assert album.items()[0].genres == ["Original Genre"]

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
        res = plugin.client._tags_for(MockPylastObj())
        assert res == ["pop", "rap"]
        res = plugin.client._tags_for(MockPylastObj(), min_weight=50)
        assert res == ["pop"]

    def test_sort_by_depth(self):
        self._setup_config(canonical=True)
        # Normal case.
        tags = ("electronic", "ambient", "post-rock", "downtempo")
        res = lastgenre.sort_by_depth(tags, self.plugin.c14n_branches)
        assert res == ["post-rock", "downtempo", "ambient", "electronic"]
        # Non-canonical tag ('chillout') present.
        tags = ("electronic", "ambient", "chillout")
        res = lastgenre.sort_by_depth(tags, self.plugin.c14n_branches)
        assert res == ["ambient", "electronic"]

    # Ignorelist tests in resolve_genres and _is_ignored

    def test_ignorelist_filters_genres_in_resolve(self):
        """Ignored genres are stripped by _resolve_genres (no c14n).

        Artist-specific and global patterns are both applied.
        """
        self._setup_config(whitelist=False, canonical=False)
        self.plugin.ignorelist = defaultdict(
            list,
            {
                "the artist": [re.compile(r"^metal$", re.IGNORECASE)],
                "*": [re.compile(r"^rock$", re.IGNORECASE)],
            },
        )
        result = self.plugin._resolve_genres(
            ["metal", "rock", "jazz"], artist="the artist"
        )
        assert "metal" not in result, (
            "artist-specific ignored genre must be removed"
        )
        assert "rock" not in result, "globally ignored genre must be removed"
        assert "jazz" in result, "non-ignored genre must survive"

    def test_ignorelist_stops_c14n_ancestry_walk(self):
        """An ignored tag's c14n parents don't bleed into the result.

        Without ignorelist, 'delta blues' canonicalizes to 'blues'.
        With 'delta blues' ignored the tag is skipped entirely in the
        c14n loop, so 'blues' must not appear either.
        """
        self._setup_config(whitelist=False, canonical=True, count=99)
        self.plugin.ignorelist = defaultdict(
            list,
            {
                "the artist": [re.compile(r"^delta blues$", re.IGNORECASE)],
            },
        )
        result = self.plugin._resolve_genres(
            ["delta blues"], artist="the artist"
        )
        assert result == [], (
            "ignored tag must not contribute c14n parents to the result"
        )

    def test_ignorelist_c14n_no_whitelist_keeps_oldest_ancestor(self):
        """With c14n on and whitelist off, ignorelist must not change the
        parent-selection rule: only the oldest ancestor is returned.
        """
        self._setup_config(whitelist=False, canonical=True, count=99)
        # ignorelist targets an unrelated genre — must not affect parent walking
        self.plugin.ignorelist = defaultdict(
            list,
            {"*": [re.compile(r"^jazz$", re.IGNORECASE)]},
        )
        result = self.plugin._resolve_genres(["delta blues"])
        assert result == ["blues"], (
            "oldest ancestor only must be returned, not the full parent chain"
        )

    def test_ignorelist_c14n_no_whitelist_drops_ignored_ancestor(self):
        """With c14n on and whitelist off, if the oldest ancestor itself is
        ignored it must be dropped and the tag contributes nothing.
        """
        self._setup_config(whitelist=False, canonical=True, count=99)
        self.plugin.ignorelist = defaultdict(
            list,
            {"*": [re.compile(r"^blues$", re.IGNORECASE)]},
        )
        result = self.plugin._resolve_genres(["delta blues"])
        assert result == [], (
            "ignored oldest ancestor must not appear in the result"
        )


@pytest.fixture
def config(config):
    """Provide a fresh beets configuration for every test/parameterize call

    This is necessary to prevent the following parameterized test to bleed
    config test state in between test cases.
    """
    return config


@pytest.mark.parametrize(
    "config_values, item_genre, mock_genres, expected_result",
    [
        # force and keep whitelisted
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
            ["Blues"],
            {
                "album": ["Jazz"],
            },
            (["Blues", "Jazz"], "keep + album, whitelist"),
        ),
        # force and keep whitelisted, unknown original
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",
                "whitelist": True,
                "canonical": False,
                "prefer_specific": False,
                "count": 10,
            },
            ["original unknown", "Blues"],
            {
                "album": ["Jazz"],
            },
            (["Blues", "Jazz"], "keep + album, whitelist"),
        ),
        # force and keep whitelisted on empty tag
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",
                "whitelist": True,
                "canonical": False,
                "prefer_specific": False,
            },
            [],
            {
                "album": ["Jazz"],
            },
            (["Jazz"], "album, whitelist"),
        ),
        # force and keep, artist configured
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "artist",  # means artist genre, original or fallback
                "whitelist": True,
                "canonical": False,
                "prefer_specific": False,
                "count": 10,
            },
            ["original unknown", "Blues"],
            {
                "album": ["Jazz"],
                "artist": ["Pop"],
            },
            (["Blues", "Pop"], "keep + artist, whitelist"),
        ),
        # don't force, disabled whitelist
        (
            {
                "force": False,
                "keep_existing": False,
                "source": "album",
                "whitelist": False,
                "canonical": False,
                "prefer_specific": False,
            },
            ["any genre"],
            {
                "album": ["Jazz"],
            },
            (["any genre"], "keep any, no-force"),
        ),
        # don't force and empty is regular last.fm fetch; no whitelist too
        (
            {
                "force": False,
                "keep_existing": False,
                "source": "album",
                "whitelist": False,
                "canonical": False,
                "prefer_specific": False,
            },
            [],
            {
                "album": ["Jazzin"],
            },
            (["Jazzin"], "album, any"),
        ),
        # Canonicalize original genre when force is **off** and
        # whitelist, canonical and cleanup_existing are on.
        # "Cosmic Disco" is not in the default whitelist, thus gets resolved "up" in the
        # tree to "Disco" and "Electronic".
        (
            {
                "force": False,
                "keep_existing": False,
                "source": "artist",
                "whitelist": True,
                "canonical": True,
                "cleanup_existing": True,
                "prefer_specific": False,
                "count": 10,
            },
            ["Cosmic Disco"],
            {
                "artist": [],
            },
            (
                ["Disco", "Electronic"],
                "keep + cleanup, whitelist",
            ),
        ),
        # fallback to next stages until found
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "track",  # means track,album,artist,...
                "whitelist": False,
                "canonical": False,
                "prefer_specific": False,
                "count": 10,
            },
            ["unknown genre"],
            {
                "track": None,
                "album": None,
                "artist": ["Jazz"],
            },
            (["Unknown Genre", "Jazz"], "keep + artist, any"),
        ),
        # Keep the original genre when force and keep_existing are on, and
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
            ["any existing"],
            {
                "track": None,
                "album": None,
                "artist": None,
            },
            (["any existing"], "original fallback"),
        ),
        # Keep the original genre when force and keep_existing are on, and
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
            ["Jazz"],
            {
                "track": None,
                "album": None,
                "artist": None,
            },
            (["Jazz"], "original fallback"),
        ),
        # Return the configured fallback when force is on but
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
            ["Jazz"],
            {
                "track": None,
                "album": None,
                "artist": None,
            },
            (["fallback genre"], "fallback"),
        ),
        # fallback to fallback if no original
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
            [],
            {
                "track": None,
                "album": None,
                "artist": None,
            },
            (["fallback genre"], "fallback"),
        ),
        # limit a lot of results
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",
                "whitelist": True,
                "count": 5,
                "canonical": False,
                "prefer_specific": False,
            },
            ["original unknown", "Blues", "Rock", "Folk", "Metal"],
            {
                "album": ["Jazz", "Bebop", "Hardbop"],
            },
            (
                ["Blues", "Rock", "Metal", "Jazz", "Bebop"],
                "keep + album, whitelist",
            ),
        ),
        # fallback to next stage (artist) if no allowed original present
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
            ["not whitelisted original"],
            {
                "track": None,
                "album": None,
                "artist": ["Jazz"],
            },
            (["Jazz"], "keep + artist, whitelist"),
        ),
        # canonicalization transforms non-whitelisted genres to canonical forms
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
            [],
            {
                "album": ["acid techno"],
            },
            (["Techno", "Electronic"], "album, whitelist"),
        ),
        # canonicalization transforms whitelisted genres to canonical forms and
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
            ["detroit techno"],
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
        # canonicalization transforms non-whitelisted original genres to canonical
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
            ["Cosmic Disco"],
            {
                "album": ["Detroit Techno"],
            },
            (
                ["Disco", "Electronic", "Detroit Techno", "Techno"],
                "keep + album, whitelist",
            ),
        ),
        # canonicalization transforms non-whitelisted original genres to canonical
        # forms and deduplication works, **even** when no new genres are found online.
        #
        # "Cosmic Disco" is not in the default whitelist, thus gets resolved "up" in the
        # tree to "Disco" and "Electronic".
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
            ["Cosmic Disco"],
            {
                "album": [],
                "artist": [],
            },
            (
                ["Disco", "Electronic"],
                "keep + original fallback, whitelist",
            ),
        ),
    ],
)
def test_get_genre(
    config, config_values, item_genre, mock_genres, expected_result
):
    """Test _get_genre with various configurations."""

    def mock_fetch_track_genre(self, trackartist, tracktitle):
        return mock_genres["track"]

    def mock_fetch_album_genre(self, albumartist, albumtitle):
        return mock_genres["album"]

    def mock_fetch_artist_genre(self, artist):
        return mock_genres["artist"]

    # Mock the last.fm fetchers. When whitelist enabled, we can assume only
    # whitelisted genres get returned, the plugin's _resolve_genre method
    # ensures it.
    lastgenre.client.LastFmClient.fetch_track_genre = mock_fetch_track_genre
    lastgenre.client.LastFmClient.fetch_album_genre = mock_fetch_album_genre
    lastgenre.client.LastFmClient.fetch_artist_genre = mock_fetch_artist_genre

    # Initialize plugin instance and item
    plugin = lastgenre.LastGenrePlugin()
    # Configure
    plugin.config.set(config_values)
    plugin.setup()  # Loads default whitelist and canonicalization tree

    item = _common.item()
    item.genres = item_genre

    # Run
    assert plugin._get_genre(item) == expected_result


# Ignorelist pattern matching tests for _is_ignored, independent of _resolve_genres


@pytest.mark.parametrize(
    "ignorelist_dict, artist, genre, expected_forbidden",
    [
        # Global ignorelist - simple word
        ({"*": ["spoken word"]}, "Any Artist", "spoken word", True),
        ({"*": ["spoken word"]}, "Any Artist", "jazz", False),
        # Global ignorelist - regex pattern
        ({"*": [".*electronic.*"]}, "Any Artist", "ambient electronic", True),
        ({"*": [".*electronic.*"]}, "Any Artist", "jazz", False),
        # Artist-specific ignorelist
        ({"metallica": ["metal"]}, "Metallica", "metal", True),
        ({"metallica": ["metal"]}, "Iron Maiden", "metal", False),
        # Case insensitive matching
        ({"metallica": ["metal"]}, "METALLICA", "METAL", True),
        # Full-match behavior: plain "metal" must not match "heavy metal"
        ({"metallica": ["metal"]}, "Metallica", "heavy metal", False),
        # Regex behavior: explicit pattern ".*metal.*" may match "heavy metal"
        ({"metallica": [".*metal.*"]}, "Metallica", "heavy metal", True),
        # Artist-specific ignorelist - exact match
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
        # Empty ignorelist
        ({}, "Any Artist", "any genre", False),
    ],
)
def test_ignorelist_patterns(
    config, ignorelist_dict, artist, genre, expected_forbidden
):
    """Test ignorelist pattern matching logic directly."""

    # Disable ignorelist to avoid depending on global config state.
    config["lastgenre"]["ignorelist"] = False

    # Initialize plugin
    plugin = lastgenre.LastGenrePlugin()

    # Set up compiled ignorelist directly (skipping file parsing)
    compiled_ignorelist = defaultdict(list)
    for artist_name, patterns in ignorelist_dict.items():
        compiled_ignorelist[artist_name.lower()] = [
            re.compile(pattern, re.IGNORECASE) for pattern in patterns
        ]

    plugin.ignorelist = compiled_ignorelist

    result = is_ignored(plugin._log, plugin.ignorelist, genre, artist)
    assert result == expected_forbidden


def test_ignorelist_literal_fallback_uses_fullmatch(config):
    """An invalid-regex pattern falls back to a literal string and must use
    full-match semantics: the pattern must equal the entire genre string,
    not just appear as a substring.
    """
    # Disable ignorelist to avoid depending on global config state.
    config["lastgenre"]["ignorelist"] = False
    plugin = lastgenre.LastGenrePlugin()
    # "[not valid regex" is not valid regex, so _compile_ignorelist_patterns
    # escapes and compiles it as a literal.
    plugin.ignorelist = lastgenre.LastGenrePlugin._compile_ignorelist_patterns(
        {"*": ["[not valid regex"]}
    )
    # Exact match must be caught.
    assert (
        is_ignored(plugin._log, plugin.ignorelist, "[not valid regex", "")
        is True
    )
    # Substring must NOT be caught (would have passed with old .search()).
    assert (
        is_ignored(
            plugin._log,
            plugin.ignorelist,
            "contains [not valid regex inside",
            "",
        )
        is False
    )


@pytest.mark.parametrize(
    "ignorelist_config, expected_ignorelist",
    [
        # Basic artist with single pattern
        ({"metallica": ["metal"]}, {"metallica": ["metal"]}),
        # Global ignorelist with '*' key
        ({"*": ["spoken word"]}, {"*": ["spoken word"]}),
        # Multiple patterns per artist
        (
            {"metallica": ["metal", ".*rock.*"]},
            {"metallica": ["metal", ".*rock.*"]},
        ),
        # Combined global and artist-specific
        (
            {"*": ["spoken word"], "metallica": ["metal"]},
            {"*": ["spoken word"], "metallica": ["metal"]},
        ),
        # Artist names are lowercased; patterns are kept as-is
        # (patterns compiled with re.IGNORECASE so case doesn't matter for matching)
        ({"METALLICA": ["METAL"]}, {"metallica": ["METAL"]}),
        # Invalid regex pattern that gets escaped (full-match literal fallback)
        ({"artist": ["[invalid(regex"]}, {"artist": ["\\[invalid\\(regex"]}),
        # Disabled via False / empty dict — both produce empty dict
        (False, {}),
        ({}, {}),
    ],
)
def test_ignorelist_config_format(
    config, ignorelist_config, expected_ignorelist
):
    """Test ignorelist parsing from beets config (dict-based)."""
    config["lastgenre"]["ignorelist"] = ignorelist_config
    plugin = lastgenre.LastGenrePlugin()

    # Convert compiled regex patterns back to strings for comparison
    string_ignorelist = {
        artist: [p.pattern for p in patterns]
        for artist, patterns in plugin.ignorelist.items()
    }

    assert string_ignorelist == expected_ignorelist


@pytest.mark.parametrize(
    "invalid_config, expected_error_message",
    [
        # A plain string (e.g. accidental file path) instead of a mapping
        (
            "/path/to/ignorelist.txt",
            "expected a mapping",
        ),
        # An integer instead of a mapping
        (
            42,
            "expected a mapping",
        ),
        # A list of strings instead of a mapping
        (
            ["spoken word", "comedy"],
            "expected a mapping",
        ),
        # A mapping with a non-list value
        (
            {"metallica": "metal"},
            "expected a list of patterns",
        ),
    ],
)
def test_ignorelist_config_format_errors(
    config, invalid_config, expected_error_message
):
    """Test ignorelist config validation error handling."""
    config["lastgenre"]["ignorelist"] = invalid_config

    with pytest.raises(UserError) as exc_info:
        lastgenre.LastGenrePlugin()

    assert expected_error_message in str(exc_info.value)


def test_ignorelist_multivalued_album_artist_fallback(config):
    """Verify ignorelist filtering for multi-valued album artist fallbacks.

    Genres already filtered for individual artists should not be dropped
    due to a secondary (incorrect) check against the combined group artist.
    """
    # Setup config: ignore 'Metal' for 'Artist A' and 'Artist Group'.
    config["lastgenre"]["ignorelist"] = {
        "Artist A": ["Metal"],
        "Artist Group": ["Metal"],
    }
    # No whitelist and larger count to keep it simple.
    config["lastgenre"]["whitelist"] = False
    config["lastgenre"]["count"] = 10

    plugin = lastgenre.LastGenrePlugin()
    plugin.setup()

    # Mock album object.
    obj = MagicMock(spec=Album)
    obj.albumartist = "Artist Group"
    obj.album = "Album Title"
    obj.albumartists = ["Artist A", "Artist B"]
    obj.get.return_value = []  # no existing genres

    # Mock client and its artist lookups.
    # We must ensure it doesn't resolve at track or album stage.
    plugin.client = MagicMock()
    plugin.client.fetch_track_genre.return_value = []
    plugin.client.fetch_album_genre.return_value = []

    # Artist lookup side effect:
    # Artist A: Returns 'Metal' and 'Rock'.
    # (Note: Client should have filtered 'Metal' already, so we simulate that by
    # returning only 'Rock').
    # Artist B: Returns 'Metal' and 'Jazz'.
    # Artist Group: Returns nothing (triggers fallback).
    def mock_fetch_artist(artist):
        if artist == "Artist A":
            return ["Rock"]
        if artist == "Artist B":
            return ["Metal", "Jazz"]
        return []

    plugin.client.fetch_artist_genre.side_effect = mock_fetch_artist

    # Note: manually triggering the logic in _get_genre.
    genres, label = plugin._get_genre(obj)

    assert "multi-valued album artist" in label
    assert "Rock" in genres
    assert "Metal" in genres  # MUST survive because Artist B allowed it
    assert "Jazz" in genres
