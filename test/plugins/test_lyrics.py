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

"""Tests for the 'lyrics' plugin."""

from functools import partial

import pytest

from beets.library import Item
from beets.test.helper import PluginMixin
from beetsplug import lyrics

from .lyrics_pages import LyricsPage, lyrics_pages

PHRASE_BY_TITLE = {
    "Lady Madonna": "friday night arrives without a suitcase",
    "Jazz'n'blues": "as i check my balance i kiss the screen",
    "Beets song": "via plugins, beets becomes a panacea",
}


class TestLyricsUtils:
    @pytest.mark.parametrize(
        "artist, title",
        [
            ("Artist", ""),
            ("", "Title"),
            (" ", ""),
            ("", " "),
            ("", ""),
        ],
    )
    def test_search_empty(self, artist, title):
        actual_pairs = lyrics.search_pairs(Item(artist=artist, title=title))

        assert not list(actual_pairs)

    @pytest.mark.parametrize(
        "artist, artist_sort, expected_extra_artists",
        [
            ("Alice ft. Bob", "", ["Alice"]),
            ("Alice feat Bob", "", ["Alice"]),
            ("Alice feat. Bob", "", ["Alice"]),
            ("Alice feats Bob", "", []),
            ("Alice featuring Bob", "", ["Alice"]),
            ("Alice & Bob", "", ["Alice"]),
            ("Alice and Bob", "", ["Alice"]),
            ("Alice", "", []),
            ("Alice", "Alice", []),
            ("Alice", "alice", []),
            ("Alice", "alice ", []),
            ("Alice", "Alice A", ["Alice A"]),
            ("CHVRCHΞS", "CHVRCHES", ["CHVRCHES"]),
            ("横山克", "Masaru Yokoyama", ["Masaru Yokoyama"]),
        ],
    )
    def test_search_pairs_artists(
        self, artist, artist_sort, expected_extra_artists
    ):
        item = Item(artist=artist, artist_sort=artist_sort, title="song")

        actual_artists = [a for a, _ in lyrics.search_pairs(item)]

        # Make sure that the original artist name is still the first entry
        assert actual_artists == [artist, *expected_extra_artists]

    @pytest.mark.parametrize(
        "title, expected_extra_titles",
        [
            ("1/2", ["1", "2"]),
            ("1 / 2", ["1", "2"]),
            ("Song (live)", ["Song"]),
            ("Song (live) (new)", ["Song"]),
            ("Song (live (new))", ["Song"]),
            ("Song ft. B", ["Song"]),
            ("Song featuring B", ["Song"]),
            ("Song and B", []),
            ("Song: B", ["Song"]),
        ],
    )
    def test_search_pairs_titles(self, title, expected_extra_titles):
        item = Item(title=title, artist="A")

        actual_titles = {
            t: None for _, tit in lyrics.search_pairs(item) for t in tit
        }

        assert list(actual_titles) == [title, *expected_extra_titles]

    @pytest.mark.parametrize(
        "initial_lyrics, expected",
        [
            ("Verse\nLyrics credit in the last line", "Verse"),
            ("Lyrics credit in the first line\nVerse", "Verse"),
            (
                """Verse
                Lyrics mentioned somewhere in the middle
                Verse""",
                """Verse
                Lyrics mentioned somewhere in the middle
                Verse""",
            ),
        ],
    )
    def test_remove_credits(self, initial_lyrics, expected):
        assert lyrics.remove_credits(initial_lyrics) == expected

    @pytest.mark.parametrize(
        "initial_text, expected",
        [
            (
                """<!--lyrics below-->
                  &nbsp;one
                  <br class='myclass'>
                  two  !
                  <br><br \\>
                  <blink>four</blink>""",
                "one\ntwo !\n\nfour",
            ),
            ("foo<script>bar</script>baz", "foobaz"),
            ("foo<!--<bar>-->qux", "fooqux"),
        ],
    )
    def test_scrape_strip_cruft(self, initial_text, expected):
        assert lyrics._scrape_strip_cruft(initial_text, True) == expected

    def test_scrape_merge_paragraphs(self):
        text = "one</p>   <p class='myclass'>two</p><p>three"
        assert lyrics._scrape_merge_paragraphs(text) == "one\ntwo\nthree"

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("test", "test"),
            ("Mørdag", "mordag"),
            ("l'été c'est fait pour jouer", "l-ete-c-est-fait-pour-jouer"),
            ("\xe7afe au lait (boisson)", "cafe-au-lait-boisson"),
            ("Multiple  spaces -- and symbols! -- merged", "multiple-spaces-and-symbols-merged"),  # noqa: E501
            ("\u200bno-width-space", "no-width-space"),
            ("El\u002dp", "el-p"),
            ("\u200bblackbear", "blackbear"),
            ("\u200d", ""),
            ("\u2010", ""),
        ],
    )  # fmt: skip
    def test_slug(self, text, expected):
        assert lyrics.slug(text) == expected


@pytest.fixture(scope="module")
def lyrics_root_dir(pytestconfig: pytest.Config):
    return pytestconfig.rootpath / "test" / "rsrc" / "lyrics"


class LyricsBackendTest(PluginMixin):
    plugin = "lyrics"

    @pytest.fixture
    def plugin_config(self):
        """Return lyrics configuration to test."""
        return {}

    @pytest.fixture
    def lyrics_plugin(self, backend_name, plugin_config):
        """Set configuration and returns the plugin's instance."""
        plugin_config["sources"] = [backend_name]
        self.config[self.plugin].set(plugin_config)

        return lyrics.LyricsPlugin()

    @pytest.fixture
    def backend(self, lyrics_plugin):
        """Return a lyrics backend instance."""
        return lyrics_plugin.backends[0]

    @pytest.fixture
    def lyrics_html(self, lyrics_root_dir, file_name):
        return (lyrics_root_dir / f"{file_name}.txt").read_text(
            encoding="utf-8"
        )


@pytest.mark.on_lyrics_update
class TestLyricsSources(LyricsBackendTest):
    @pytest.fixture(scope="class")
    def plugin_config(self):
        return {"google_API_key": "test", "synced": True}

    @pytest.fixture(
        params=[pytest.param(lp, marks=lp.marks) for lp in lyrics_pages],
        ids=str,
    )
    def lyrics_page(self, request):
        return request.param

    @pytest.fixture
    def backend_name(self, lyrics_page):
        return lyrics_page.backend

    @pytest.fixture(autouse=True)
    def _patch_google_search(self, requests_mock, lyrics_page):
        """Mock the Google Search API to return the lyrics page under test."""
        requests_mock.real_http = True

        data = {
            "items": [
                {
                    "title": lyrics_page.url_title,
                    "link": lyrics_page.url,
                    "displayLink": lyrics_page.root_url,
                }
            ]
        }
        requests_mock.get(lyrics.Google.SEARCH_URL, json=data)

    def test_backend_source(self, lyrics_plugin, lyrics_page: LyricsPage):
        """Test parsed lyrics from each of the configured lyrics pages."""
        lyrics = lyrics_plugin.get_lyrics(
            lyrics_page.artist, lyrics_page.track_title, "", 0
        )

        assert lyrics
        assert lyrics == lyrics_page.lyrics


class TestGoogleLyrics(LyricsBackendTest):
    """Test scraping heuristics on a fake html page."""

    TITLE = "Beets song"

    @pytest.fixture(scope="class")
    def backend_name(self):
        return "google"

    @pytest.fixture(scope="class")
    def plugin_config(self):
        return {"google_API_key": "test"}

    @pytest.fixture(scope="class")
    def file_name(self):
        return "examplecom/beetssong"

    def test_mocked_source_ok(self, backend, lyrics_html):
        """Test that lyrics of the mocked page are correctly scraped"""
        result = lyrics.scrape_lyrics_from_html(lyrics_html).lower()

        assert result
        assert backend.is_lyrics(result)
        assert PHRASE_BY_TITLE[self.TITLE] in result

    @pytest.mark.parametrize(
        "url_title, artist, should_be_candidate",
        [
            ("John Doe - beets song Lyrics", "John Doe", True),
            ("example.com | Beats song by John doe", "John Doe", True),
            ("example.com | seets bong lyrics by John doe", "John Doe", False),
            ("foo", "Sun O)))", False),
        ],
    )
    def test_is_page_candidate(
        self, backend, lyrics_html, url_title, artist, should_be_candidate
    ):
        result = backend.is_page_candidate(
            "http://www.example.com/lyrics/beetssong",
            url_title,
            self.TITLE,
            artist,
        )
        assert bool(result) == should_be_candidate

    @pytest.mark.parametrize(
        "lyrics",
        [
            "LyricsMania.com - Copyright (c) 2013 - All Rights Reserved",
            """All material found on this site is property\n
                     of mywickedsongtext brand""",
            """
Lyricsmania staff is working hard for you to add $TITLE lyrics as soon
as they'll be released by $ARTIST, check back soon!
In case you have the lyrics to $TITLE and want to send them to us, fill out
the following form.
""",
        ],
    )
    def test_bad_lyrics(self, backend, lyrics):
        assert not backend.is_lyrics(lyrics)

    def test_slugify(self, backend):
        text = "http://site.com/\xe7afe-au_lait(boisson)"
        assert backend.slugify(text) == "http://site.com/cafe_au_lait"


class TestGeniusLyrics(LyricsBackendTest):
    @pytest.fixture(scope="class")
    def backend_name(self):
        return "genius"

    @pytest.mark.parametrize(
        "file_name, expected_line_count",
        [
            ("geniuscom/2pacalleyezonmelyrics", 134),
            ("geniuscom/Ttngchinchillalyrics", 29),
            ("geniuscom/sample", 0),  # see https://github.com/beetbox/beets/issues/3535
        ],
    )  # fmt: skip
    def test_scrape(self, backend, lyrics_html, expected_line_count):
        result = backend._scrape_lyrics_from_html(lyrics_html) or ""

        assert len(result.splitlines()) == expected_line_count


class TestTekstowoLyrics(LyricsBackendTest):
    @pytest.fixture(scope="class")
    def backend_name(self):
        return "tekstowo"

    @pytest.mark.parametrize(
        "file_name, expecting_lyrics",
        [
            ("tekstowopl/piosenka24kgoldncityofangels1", True),
            (
                "tekstowopl/piosenkabeethovenbeethovenpianosonata17tempestthe3rdmovement",  # noqa: E501
                False,
            ),
        ],
    )
    def test_scrape(self, backend, lyrics_html, expecting_lyrics):
        assert bool(backend.extract_lyrics(lyrics_html)) == expecting_lyrics


class TestLRCLibLyrics(LyricsBackendTest):
    @pytest.fixture(scope="class")
    def backend_name(self):
        return "lrclib"

    @pytest.fixture
    def fetch_lyrics(self, backend, requests_mock, response_data):
        requests_mock.get(lyrics.LRCLib.base_url, json=response_data)

        return partial(backend.fetch, "la", "la", "la", 0)

    @pytest.mark.parametrize(
        "response_data",
        [
            {
                "syncedLyrics": "[00:00.00] la la la",
                "plainLyrics": "la la la",
            }
        ],
    )
    @pytest.mark.parametrize(
        "plugin_config, expected_lyrics",
        [
            ({"synced": True}, "[00:00.00] la la la"),
            ({"synced": False}, "la la la"),
        ],
    )
    def test_synced_config_option(self, fetch_lyrics, expected_lyrics):
        assert fetch_lyrics() == expected_lyrics

    @pytest.mark.parametrize(
        "response_data, expected_lyrics",
        [
            pytest.param(
                {"syncedLyrics": "", "plainLyrics": "la la la"},
                "la la la",
                id="pick plain lyrics",
            ),
            pytest.param(
                {
                    "statusCode": 404,
                    "error": "Not Found",
                    "message": "Failed to find specified track",
                },
                None,
                id="not found",
            ),
        ],
    )
    def test_fetch_lyrics(self, fetch_lyrics, expected_lyrics):
        assert fetch_lyrics() == expected_lyrics
