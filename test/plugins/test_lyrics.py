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

import os
from functools import partial

import pytest

from beets.library import Item
from beets.test.helper import PluginMixin
from beetsplug import lyrics

PHRASE_BY_TITLE = {
    "Lady Madonna": "friday night arrives without a suitcase",
    "Jazz'n'blues": "as i check my balance i kiss the screen",
    "Beets song": "via plugins, beets becomes a panacea",
}

_p = pytest.param


def xfail_on_ci(msg: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(
        bool(os.environ.get("GITHUB_ACTIONS")),
        reason=msg,
        raises=AssertionError,
    )


class TestLyricsUtils:
    def test_search_artist(self):
        item = Item(artist="Alice ft. Bob", title="song")
        assert ("Alice ft. Bob", ["song"]) in lyrics.search_pairs(item)
        assert ("Alice", ["song"]) in lyrics.search_pairs(item)

        item = Item(artist="Alice feat Bob", title="song")
        assert ("Alice feat Bob", ["song"]) in lyrics.search_pairs(item)
        assert ("Alice", ["song"]) in lyrics.search_pairs(item)

        item = Item(artist="Alice feat. Bob", title="song")
        assert ("Alice feat. Bob", ["song"]) in lyrics.search_pairs(item)
        assert ("Alice", ["song"]) in lyrics.search_pairs(item)

        item = Item(artist="Alice feats Bob", title="song")
        assert ("Alice feats Bob", ["song"]) in lyrics.search_pairs(item)
        assert ("Alice", ["song"]) not in lyrics.search_pairs(item)

        item = Item(artist="Alice featuring Bob", title="song")
        assert ("Alice featuring Bob", ["song"]) in lyrics.search_pairs(item)
        assert ("Alice", ["song"]) in lyrics.search_pairs(item)

        item = Item(artist="Alice & Bob", title="song")
        assert ("Alice & Bob", ["song"]) in lyrics.search_pairs(item)
        assert ("Alice", ["song"]) in lyrics.search_pairs(item)

        item = Item(artist="Alice and Bob", title="song")
        assert ("Alice and Bob", ["song"]) in lyrics.search_pairs(item)
        assert ("Alice", ["song"]) in lyrics.search_pairs(item)

        item = Item(artist="Alice and Bob", title="song")
        assert ("Alice and Bob", ["song"]) == list(lyrics.search_pairs(item))[0]

    def test_search_artist_sort(self):
        item = Item(artist="CHVRCHΞS", title="song", artist_sort="CHVRCHES")
        assert ("CHVRCHΞS", ["song"]) in lyrics.search_pairs(item)
        assert ("CHVRCHES", ["song"]) in lyrics.search_pairs(item)

        # Make sure that the original artist name is still the first entry
        assert ("CHVRCHΞS", ["song"]) == list(lyrics.search_pairs(item))[0]

        item = Item(
            artist="横山克", title="song", artist_sort="Masaru Yokoyama"
        )
        assert ("横山克", ["song"]) in lyrics.search_pairs(item)
        assert ("Masaru Yokoyama", ["song"]) in lyrics.search_pairs(item)

        # Make sure that the original artist name is still the first entry
        assert ("横山克", ["song"]) == list(lyrics.search_pairs(item))[0]

    def test_search_pairs_multi_titles(self):
        item = Item(title="1 / 2", artist="A")
        assert ("A", ["1 / 2"]) in lyrics.search_pairs(item)
        assert ("A", ["1", "2"]) in lyrics.search_pairs(item)

        item = Item(title="1/2", artist="A")
        assert ("A", ["1/2"]) in lyrics.search_pairs(item)
        assert ("A", ["1", "2"]) in lyrics.search_pairs(item)

    def test_search_pairs_titles(self):
        item = Item(title="Song (live)", artist="A")
        assert ("A", ["Song"]) in lyrics.search_pairs(item)
        assert ("A", ["Song (live)"]) in lyrics.search_pairs(item)

        item = Item(title="Song (live) (new)", artist="A")
        assert ("A", ["Song"]) in lyrics.search_pairs(item)
        assert ("A", ["Song (live) (new)"]) in lyrics.search_pairs(item)

        item = Item(title="Song (live (new))", artist="A")
        assert ("A", ["Song"]) in lyrics.search_pairs(item)
        assert ("A", ["Song (live (new))"]) in lyrics.search_pairs(item)

        item = Item(title="Song ft. B", artist="A")
        assert ("A", ["Song"]) in lyrics.search_pairs(item)
        assert ("A", ["Song ft. B"]) in lyrics.search_pairs(item)

        item = Item(title="Song featuring B", artist="A")
        assert ("A", ["Song"]) in lyrics.search_pairs(item)
        assert ("A", ["Song featuring B"]) in lyrics.search_pairs(item)

        item = Item(title="Song and B", artist="A")
        assert ("A", ["Song and B"]) in lyrics.search_pairs(item)
        assert ("A", ["Song"]) not in lyrics.search_pairs(item)

        item = Item(title="Song: B", artist="A")
        assert ("A", ["Song"]) in lyrics.search_pairs(item)
        assert ("A", ["Song: B"]) in lyrics.search_pairs(item)

    def test_remove_credits(self):
        assert (
            lyrics.remove_credits(
                """It's close to midnight
                                     Lyrics brought by example.com"""
            )
            == "It's close to midnight"
        )
        assert lyrics.remove_credits("""Lyrics brought by example.com""") == ""

        # don't remove 2nd verse for the only reason it contains 'lyrics' word
        text = """Look at all the shit that i done bought her
                  See lyrics ain't nothin
                  if the beat aint crackin"""
        assert lyrics.remove_credits(text) == text

    def test_scrape_strip_cruft(self):
        text = """<!--lyrics below-->
                  &nbsp;one
                  <br class='myclass'>
                  two  !
                  <br><br \\>
                  <blink>four</blink>"""
        assert lyrics._scrape_strip_cruft(text, True) == "one\ntwo !\n\nfour"

    def test_scrape_strip_scripts(self):
        text = """foo<script>bar</script>baz"""
        assert lyrics._scrape_strip_cruft(text, True) == "foobaz"

    def test_scrape_strip_tag_in_comment(self):
        text = """foo<!--<bar>-->qux"""
        assert lyrics._scrape_strip_cruft(text, True) == "fooqux"

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
    def backend(self, backend_name, plugin_config):
        """Set configuration and returns the backend instance."""
        plugin_config["sources"] = [backend_name]
        self.config[self.plugin].set(plugin_config)

        lyrics_plugin = lyrics.LyricsPlugin()
        return lyrics_plugin.backends[0]

    @pytest.fixture
    def lyrics_html(self, lyrics_root_dir, file_name):
        return (lyrics_root_dir / f"{file_name}.txt").read_text(
            encoding="utf-8"
        )

    @pytest.mark.on_lyrics_update
    def test_backend_source(self, backend):
        """Test default backends with a song known to exist in respective
        databases.
        """
        title = "Lady Madonna"

        lyrics = backend.fetch("The Beatles", title)

        assert lyrics
        assert PHRASE_BY_TITLE[title] in lyrics.lower()


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

    @pytest.mark.on_lyrics_update
    @pytest.mark.parametrize(
        "title, url",
        [
            *(
                ("Lady Madonna", url)
                for url in (
                    "http://www.chartlyrics.com/_LsLsZ7P4EK-F-LD4dJgDQ/Lady+Madonna.aspx",  # noqa: E501
                    "http://www.absolutelyrics.com/lyrics/view/the_beatles/lady_madonna",  # noqa: E501
                    "https://www.letras.mus.br/the-beatles/275/",
                    "https://www.lyricsmania.com/lady_madonna_lyrics_the_beatles.html",
                    "https://www.lyricsmode.com/lyrics/b/beatles/lady_madonna.html",
                    "https://www.paroles.net/the-beatles/paroles-lady-madonna",
                    "https://www.songlyrics.com/the-beatles/lady-madonna-lyrics/",
                    "https://sweetslyrics.com/the-beatles/lady-madonna-lyrics",
                    "https://www.musica.com/letras.asp?letra=59862",
                    "https://www.lacoccinelle.net/259956-the-beatles-lady-madonna.html",
                )
            ),
            _p(
                "Lady Madonna",
                "https://www.azlyrics.com/lyrics/beatles/ladymadonna.html",
                marks=xfail_on_ci("AZLyrics is blocked by Cloudflare"),
            ),
            (
                "Jazz'n'blues",
                "https://www.lyricsontop.com/amy-winehouse-songs/jazz-n-blues-lyrics.html",  # noqa: E501
            ),
        ],
    )
    def test_backend_source(self, backend, title, url):
        """Test if lyrics present on websites registered in beets google custom
        search engine are correctly scraped.
        """
        response = backend.fetch_url(url)
        result = lyrics.scrape_lyrics_from_html(response).lower()

        assert backend.is_lyrics(result)
        assert PHRASE_BY_TITLE[title] in result

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

    @pytest.mark.on_lyrics_update
    @xfail_on_ci("Genius returns 403 FORBIDDEN in CI")
    def test_backend_source(self, backend):
        super().test_backend_source(backend)

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

        return partial(backend.fetch, "la", "la", "la")

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
            _p(
                {"syncedLyrics": "", "plainLyrics": "la la la"},
                "la la la",
                id="pick plain lyrics",
            ),
            _p(
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
