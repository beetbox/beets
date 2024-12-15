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

from unittest.mock import Mock

from beets import config
from beets.test import _common
from beets.test.helper import BeetsTestCase
from beetsplug import lastgenre


class LastGenrePluginTest(BeetsTestCase):
    def setUp(self):
        super().setUp()
        self.plugin = lastgenre.LastGenrePlugin()

    def _setup_config(
        self, whitelist=False, canonical=False, count=1, prefer_specific=False
    ):
        config["lastgenre"]["canonical"] = canonical
        config["lastgenre"]["count"] = count
        config["lastgenre"]["prefer_specific"] = prefer_specific
        if isinstance(whitelist, (bool, (str,))):
            # Filename, default, or disabled.
            config["lastgenre"]["whitelist"] = whitelist
        self.plugin.setup()
        if not isinstance(whitelist, (bool, (str,))):
            # Explicit list of genres.
            self.plugin.whitelist = whitelist

    def test_default(self):
        """Fetch genres with whitelist and c14n deactivated"""
        self._setup_config()
        assert self.plugin._resolve_genres(["delta blues"]) == "Delta Blues"

    def test_c14n_only(self):
        """Default c14n tree funnels up to most common genre except for *wrong*
        genres that stay unchanged.
        """
        self._setup_config(canonical=True, count=99)
        assert self.plugin._resolve_genres(["delta blues"]) == "Blues"
        assert self.plugin._resolve_genres(["iota blues"]) == "Iota Blues"

    def test_whitelist_only(self):
        """Default whitelist rejects *wrong* (non existing) genres."""
        self._setup_config(whitelist=True)
        assert self.plugin._resolve_genres(["iota blues"]) == ""

    def test_whitelist_c14n(self):
        """Default whitelist and c14n both activated result in all parents
        genres being selected (from specific to common).
        """
        self._setup_config(canonical=True, whitelist=True, count=99)
        assert (
            self.plugin._resolve_genres(["delta blues"]) == "Delta Blues, Blues"
        )

    def test_whitelist_custom(self):
        """Keep only genres that are in the whitelist."""
        self._setup_config(whitelist={"blues", "rock", "jazz"}, count=2)
        assert self.plugin._resolve_genres(["pop", "blues"]) == "Blues"

        self._setup_config(canonical="", whitelist={"rock"})
        assert self.plugin._resolve_genres(["delta blues"]) == ""

    def test_count(self):
        """Keep the n first genres, as we expect them to be sorted from more to
        less popular.
        """
        self._setup_config(whitelist={"blues", "rock", "jazz"}, count=2)
        assert (
            self.plugin._resolve_genres(["jazz", "pop", "rock", "blues"])
            == "Jazz, Rock"
        )

    def test_count_c14n(self):
        """Keep the n first genres, after having applied c14n when necessary"""
        self._setup_config(
            whitelist={"blues", "rock", "jazz"}, canonical=True, count=2
        )
        # thanks to c14n, 'blues' superseeds 'country blues' and takes the
        # second slot
        assert (
            self.plugin._resolve_genres(
                ["jazz", "pop", "country blues", "rock"]
            )
            == "Jazz, Blues"
        )

    def test_c14n_whitelist(self):
        """Genres first pass through c14n and are then filtered"""
        self._setup_config(canonical=True, whitelist={"rock"})
        assert self.plugin._resolve_genres(["delta blues"]) == ""

    def test_empty_string_enables_canonical(self):
        """For backwards compatibility, setting the `canonical` option
        to the empty string enables it using the default tree.
        """
        self._setup_config(canonical="", count=99)
        assert self.plugin._resolve_genres(["delta blues"]) == "Blues"

    def test_empty_string_enables_whitelist(self):
        """Again for backwards compatibility, setting the `whitelist`
        option to the empty string enables the default set of genres.
        """
        self._setup_config(whitelist="")
        assert self.plugin._resolve_genres(["iota blues"]) == ""

    def test_prefer_specific_loads_tree(self):
        """When prefer_specific is enabled but canonical is not the
        tree still has to be loaded.
        """
        self._setup_config(prefer_specific=True, canonical=False)
        assert self.plugin.c14n_branches != []

    def test_prefer_specific_without_canonical(self):
        """Prefer_specific works without canonical."""
        self._setup_config(prefer_specific=True, canonical=False, count=4)
        assert (
            self.plugin._resolve_genres(["math rock", "post-rock"])
            == "Post-Rock, Math Rock"
        )

    def test_no_duplicate(self):
        """Remove duplicated genres."""
        self._setup_config(count=99)
        assert self.plugin._resolve_genres(["blues", "blues"]) == "Blues"

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

    def test_get_genre(self):
        """All possible (genre, label) pairs"""
        mock_genres = {"track": "1", "album": "2", "artist": "3"}

        def mock_fetch_track_genre(self, obj=None):
            return mock_genres["track"]

        def mock_fetch_album_genre(self, obj):
            return mock_genres["album"]

        def mock_fetch_artist_genre(self, obj):
            return mock_genres["artist"]

        lastgenre.LastGenrePlugin.fetch_track_genre = mock_fetch_track_genre
        lastgenre.LastGenrePlugin.fetch_album_genre = mock_fetch_album_genre
        lastgenre.LastGenrePlugin.fetch_artist_genre = mock_fetch_artist_genre

        self._setup_config(whitelist=False)
        item = _common.item()
        item.genre = mock_genres["track"]

        # The default setting
        config["lastgenre"] = {"force": False, "keep_allowed": True}
        res = self.plugin._get_genre(item)
        assert res == (item.genre, "keep allowed")

        # Not forcing and keeping any existing
        config["lastgenre"] = {"force": False, "keep_allowed": False}
        res = self.plugin._get_genre(item)
        assert res == (item.genre, "keep any")

        # Track
        config["lastgenre"] = {"force": True, "keep_allowed": False, "source": "track"}
        res = self.plugin._get_genre(item)
        assert res == (mock_genres["track"], "track")

        config["lastgenre"] = {"force": True, "keep_allowed": True, "source": "track"}
        res = self.plugin._get_genre(item)
        assert res == (mock_genres["track"], "keep + track")
        print("res after track check:", res)

        # Album
        config["lastgenre"] = {"source": "album", "keep_allowed": False}
        res = self.plugin._get_genre(item)
        print("res is:", res)
        print("mock_genres is:", mock_genres["album"])
        assert res == (mock_genres["album"], "album")

        config["lastgenre"] = {"source": "album", "keep_allowed": True}
        res = self.plugin._get_genre(item)
        assert res == (mock_genres["album"], "keep + album")

        # Artist
        config["lastgenre"] = {"source": "artist", "keep_allowed": False}
        res = self.plugin._get_genre(item)
        assert res == (mock_genres["artist"], "artist")

        config["lastgenre"] = {"source": "artist", "keep_allowed": True}
        res = self.plugin._get_genre(item)
        assert res == (mock_genres["artist"], "keep + artist")

        # Original
        mock_genres["artist"] = None
        res = self.plugin._get_genre(item)
        assert res == (item.genre, "original")

        # Fallback
        config["lastgenre"] = {"fallback": "rap", "keep_allowed": False}
        item.genre = None
        res = self.plugin._get_genre(item)
        assert res == (config["lastgenre"]["fallback"].get(), "fallback")

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
