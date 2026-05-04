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
from unittest.mock import Mock, patch

import confuse
import pytest

from beets.library import Album
from beets.test import _common
from beets.test.helper import IOMixin, PluginTestCase
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

    def test_fetch_genre(self):
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
        res = plugin.client.fetch_genres(MockPylastObj())
        assert res == ["pop", "rap"]

        plugin.client._min_weight = 50
        res = plugin.client.fetch_genres(MockPylastObj())
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
        self.plugin.ignore_patterns = defaultdict(
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
        self.plugin.ignore_patterns = defaultdict(
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
        self.plugin.ignore_patterns = defaultdict(
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
        self.plugin.ignore_patterns = defaultdict(
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
        # Semicolon-delimited genre tag from an external mediafile
        # ("Jazz; Funk; Soul" as a single element) is split by
        # DelimitedString.normalize() on assignment and returned as three
        # individual genres via the "original fallback" path when all Last.fm
        # stages return empty.
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",
                "whitelist": False,
                "canonical": False,
                "prefer_specific": False,
                "count": 10,
            },
            ["Jazz; Funk; Soul"],
            {
                "album": [],
                "artist": [],
            },
            (["Jazz", "Funk", "Soul"], "original fallback"),
        ),
        # Multiple whitelisted genres in the multi-valued `genres` field must
        # NOT be wiped when Last.fm returns no tags — whether the album is not
        # found at all or exists but has no tags. Both scenarios produce an
        # empty list from the fetcher and must be preserved via "original
        # fallback".
        (
            {
                "force": True,
                "keep_existing": True,
                "source": "album",
                "whitelist": True,
                "canonical": False,
                "prefer_specific": False,
            },
            ["Baroque", "Classical"],
            {
                "album": [],
                "artist": [],
            },
            (["Baroque", "Classical"], "original fallback"),
        ),
    ],
)
@pytest.mark.usefixtures("config")
def test_get_genre(
    monkeypatch, config_values, item_genre, mock_genres, expected_result
):
    """Test _get_genre with various configurations."""
    # Mock the last.fm fetchers. When whitelist enabled, we can assume only
    # whitelisted genres get returned, the plugin's _resolve_genre method
    # ensures it.
    monkeypatch.setattr(
        "beetsplug.lastgenre.client.LastFmClient.fetch",
        lambda _, kind, __: mock_genres[kind],
    )
    # Initialize plugin instance and item
    plugin = lastgenre.LastGenrePlugin()
    # Configure
    plugin.config.set(config_values)
    plugin.setup()  # Loads default whitelist and canonicalization tree

    item = _common.item()
    item.genres = item_genre

    # Run
    assert plugin._get_genre(item) == expected_result


class TestIgnorelist:
    """Ignorelist pattern matching tests independent of resolve_genres."""

    @pytest.mark.parametrize(
        "ignorelist_dict, artist, genre, expected_forbidden",
        [
            # Global ignorelist - simple word
            ({"*": ["spoken word"]}, "Any Artist", "spoken word", True),
            ({"*": ["spoken word"]}, "Any Artist", "jazz", False),
            # Global ignorelist - regex pattern
            (
                {"*": [".*electronic.*"]},
                "Any Artist",
                "ambient electronic",
                True,
            ),
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
            (
                {"metallica": ["^Heavy Metal$"]},
                "Metallica",
                "classic metal",
                False,
            ),
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
        self, ignorelist_dict, artist, genre, expected_forbidden
    ):
        """Test ignorelist pattern matching logic directly."""

        logger = Mock()

        # Set up compiled ignorelist directly (skipping file parsing)
        compiled_ignorelist = defaultdict(list)
        for artist_name, patterns in ignorelist_dict.items():
            compiled_ignorelist[artist_name.lower()] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]

        result = is_ignored(logger, compiled_ignorelist, genre, artist)
        assert result == expected_forbidden

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
            # Artist names are preserved by the current loader implementation.
            ({"METALLICA": ["METAL"]}, {"METALLICA": ["METAL"]}),
            # Invalid regex pattern that gets escaped (full-match literal fallback)
            (
                {"artist": ["[invalid(regex"]},
                {"artist": ["\\[invalid\\(regex"]},
            ),
            # Disabled via False / empty dict — both produce empty dict
            (False, {}),
            ({}, {}),
        ],
    )
    def test_ignorelist_config_format(
        self, ignorelist_config, expected_ignorelist
    ):
        """Test ignorelist parsing/compilation with isolated config state."""
        cfg = confuse.Configuration("test", read=False)
        cfg.set({"lastgenre": {"ignorelist": ignorelist_config}})

        # Mimic the plugin loader behavior in isolation to avoid global config bleed.
        if not cfg["lastgenre"]["ignorelist"].get():
            string_ignorelist = {}
        else:
            raw_strs = cfg["lastgenre"]["ignorelist"].get(
                confuse.MappingValues(confuse.Sequence(str))
            )
            string_ignorelist = {}
            for artist, patterns in raw_strs.items():
                compiled_patterns = []
                for pattern in patterns:
                    try:
                        compiled_patterns.append(
                            re.compile(pattern, re.IGNORECASE).pattern
                        )
                    except re.error:
                        compiled_patterns.append(
                            re.compile(
                                re.escape(pattern), re.IGNORECASE
                            ).pattern
                        )
                string_ignorelist[artist] = compiled_patterns

        assert string_ignorelist == expected_ignorelist

    @pytest.mark.parametrize(
        "invalid_config, expected_error_message",
        [
            # A plain string (e.g. accidental file path) instead of a mapping
            (
                "/path/to/ignorelist.txt",
                "must be a dict",
            ),
            # An integer instead of a mapping
            (
                42,
                "must be a dict",
            ),
            # A list of strings instead of a mapping
            (
                ["spoken word", "comedy"],
                "must be a dict",
            ),
            # A mapping with a non-list value
            (
                {"metallica": "metal"},
                "must be a list",
            ),
        ],
    )
    def test_ignorelist_config_format_errors(
        self, invalid_config, expected_error_message
    ):
        """Test ignorelist config validation errors in isolated config."""
        cfg = confuse.Configuration("test", read=False)
        cfg.set({"lastgenre": {"ignorelist": invalid_config}})

        with pytest.raises(confuse.ConfigTypeError) as exc_info:
            _ = cfg["lastgenre"]["ignorelist"].get(
                confuse.MappingValues(confuse.Sequence(str))
            )

        assert expected_error_message in str(exc_info.value)

    def test_ignorelist_multivalued_album_artist_fallback(
        self, monkeypatch, config
    ):
        """`stage_artist=None` fallback must not re-drop per-artist results."""
        config["lastgenre"]["ignorelist"] = {
            "Artist A": ["Metal"],
            "Artist Group": ["Metal"],
        }
        config["lastgenre"]["whitelist"] = False
        config["lastgenre"]["count"] = 10

        plugin = lastgenre.LastGenrePlugin()
        plugin.setup()

        def fake_fetch(_, kind, obj, *args):
            if kind == "album_artist" and args:
                album_artist = args[0]
                return {
                    "Artist A": ["Rock"],
                    "Artist B": ["Metal", "Jazz"],
                }[album_artist]
            return []

        monkeypatch.setattr(
            "beetsplug.lastgenre.client.LastFmClient.fetch", fake_fetch
        )

        obj = Album()
        obj.albumartist = "Artist Group"
        obj.album = "Album Title"
        obj.albumartists = ["Artist A", "Artist B"]

        genres, label = plugin._get_genre(obj)

        assert "multi-valued album artist" in label
        assert "Metal" in genres
