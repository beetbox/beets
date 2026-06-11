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

from __future__ import annotations

import logging
import re
import textwrap
from functools import partial
from http import HTTPStatus
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
import requests

from beets.library import Item
from beets.test.helper import PluginMixin, TestHelper
from beets.util.lyrics import Lyrics
from beetsplug import lyrics

from .lyrics_pages import lyrics_pages

if TYPE_CHECKING:
    from pathlib import Path

    from .lyrics_pages import LyricsPage

PHRASE_BY_TITLE = {
    "Lady Madonna": "friday night arrives without a suitcase",
    "Jazz'n'blues": "as i check my balance i kiss the screen",
    "Beets song": "via plugins, beets becomes a panacea",
}


@pytest.fixture(scope="module")
def helper():
    helper = TestHelper()
    helper.setup_beets()
    yield helper
    helper.teardown_beets()


class TestLyricsUtils:
    @pytest.mark.parametrize(
        "artist, title",
        [
            ("Various Artists", "Title"),
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
            ("1/2", []),
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

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("If They’re Shooting at You", "If-They-re-Shooting-at-You"),
            ("‘Round Midnight", "-Round-Midnight"),
            ("Don't Stop", "Don-t-Stop"),
        ],
    )
    def test_musixmatch_encode(self, text, expected):
        assert lyrics.MusiXmatch.encode(text) == expected


class TestHtml:
    def test_scrape_strip_cruft(self):
        initial = """<!--lyrics below-->
                  &nbsp;one
                  <br class='myclass'>
                  two  !
                  <br><br \\>
                  <blink>four</blink>"""
        expected = "<!--lyrics below-->\none\ntwo !\n\n<blink>four</blink>"

        assert lyrics.Html.normalize_space(initial) == expected

    def test_scrape_merge_paragraphs(self):
        text = 'one</p><p class="myclass"></p><p>two</p><p>three'
        expected = "one\n\ntwo\n\nthree"

        assert lyrics.Html.merge_paragraphs(text) == expected


class TestSearchBackend:
    @pytest.fixture
    def backend(self, dist_thresh):
        plugin = lyrics.LyricsPlugin()
        plugin.config.set({"dist_thresh": dist_thresh})
        return lyrics.SearchBackend(plugin.config, plugin._log)

    @pytest.mark.parametrize(
        "dist_thresh, target_artist, artist, should_match",
        [
            (0.11, "Target Artist", "Target Artist", True),
            (0.11, "Target Artist", "Target Artis", True),
            (0.11, "Target Artist", "Target Arti", False),
            (0.11, "Psychonaut", "Psychonaut (BEL)", True),
            (0.11, "beets song", "beats song", True),
            (0.10, "beets song", "beats song", False),
            (
                0.11,
                "Lucid Dreams (Forget Me)",
                "Lucid Dreams (Remix) ft. Lil Uzi Vert",
                False,
            ),
            (
                0.12,
                "Lucid Dreams (Forget Me)",
                "Lucid Dreams (Remix) ft. Lil Uzi Vert",
                True,
            ),
        ],
    )
    def test_check_match(self, backend, target_artist, artist, should_match):
        result = lyrics.SearchResult(artist, "", "")

        assert backend.check_match(target_artist, "", result) == should_match


@pytest.fixture(scope="module")
def lyrics_root_dir(pytestconfig: pytest.Config):
    return pytestconfig.rootpath / "test" / "rsrc" / "lyrics"


class LyricsPluginMixin(PluginMixin):
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


class TestLyricsPlugin(LyricsPluginMixin):
    @pytest.fixture
    def backend_name(self):
        """Return lyrics configuration to test."""
        return "lrclib"

    @pytest.mark.parametrize(
        "request_kwargs, expected_log_match",
        [
            (
                {"status_code": HTTPStatus.BAD_GATEWAY},
                r"LRCLib: Request error: 502",
            ),
            ({"text": "invalid"}, r"LRCLib: Could not decode.*JSON"),
        ],
    )
    def test_error_handling(
        self,
        requests_mock,
        lyrics_plugin,
        caplog,
        request_kwargs,
        expected_log_match,
    ):
        """Errors are logged with the backend name."""
        requests_mock.get(lyrics.LRCLib.SEARCH_URL, **request_kwargs)

        assert lyrics_plugin.get_lyrics("", "", "", 0.0) is None
        assert caplog.messages
        last_log = caplog.messages[-1]
        assert last_log
        assert re.search(expected_log_match, last_log, re.I)

    @pytest.mark.parametrize(
        "plugin_config, old_lyrics, found, expected",
        [
            pytest.param({}, "old", "new", "old", id="no_force_keeps_old"),
            pytest.param(
                {"force": True},
                "old",
                "new",
                "new",
                id="force_overwrites_with_new",
            ),
            pytest.param(
                {"force": True, "local": True},
                "old",
                "new",
                "old",
                id="force_local_keeps_old",
            ),
            pytest.param(
                {"force": True, "fallback": None},
                "old",
                None,
                "old",
                id="force_fallback_none_keeps_old",
            ),
            pytest.param(
                {"force": True, "fallback": ""},
                "old",
                None,
                "",
                id="force_fallback_empty_uses_empty",
            ),
            pytest.param(
                {"force": True, "fallback": "default"},
                "old",
                None,
                "default",
                id="force_fallback_default_uses_default",
            ),
            pytest.param(
                {"force": True, "synced": True},
                "[00:00.00] old synced",
                "new plain",
                "[00:00.00] old synced",
                id="keep-existing-synced-lyrics",
            ),
            pytest.param(
                {"force": True, "synced": True},
                "[00:00.00] old synced",
                "[00:00.00] new synced",
                "[00:00.00] new synced",
                id="replace-with-new-synced-lyrics",
            ),
            pytest.param(
                {"force": True, "synced": False},
                "[00:00.00] old synced",
                "new plain",
                "new plain",
                id="replace-with-unsynced-lyrics-when-disabled",
            ),
            pytest.param(
                {"force": True, "keep_synced": True},
                "[00:00.00] old synced",
                "new",
                "[00:00.00] old synced",
                id="keep_synced_keeps_old_synced",
            ),
        ],
    )
    def test_overwrite_config(
        self, monkeypatch, helper, lyrics_plugin, old_lyrics, found, expected
    ):
        monkeypatch.setattr(
            lyrics_plugin,
            "find_lyrics",
            lambda _: Lyrics(found) if found is not None else None,
        )
        item = helper.create_item(id=1, lyrics=old_lyrics)

        lyrics_plugin.add_item_lyrics(item, False)

        assert item.lyrics == expected

    def test_set_additional_lyrics_info(
        self, monkeypatch, helper, lyrics_plugin, is_importable
    ):
        lyrics = Lyrics(
            "sing in the rain every hour of the day",
            "lrclib",
            url="https://lrclib.net/api/1",
        )
        monkeypatch.setattr(lyrics_plugin, "find_lyrics", lambda _: lyrics)
        item = helper.add_item(
            id=1, lyrics="", lyrics_translation_language="EN"
        )

        lyrics_plugin.add_item_lyrics(item, False)

        item = helper.lib.get_item(item.id)

        assert item.lyrics_url == lyrics.url
        assert item.lyrics_backend == lyrics.backend
        if is_importable("langdetect"):
            assert item.lyrics_language == "EN"
        else:
            with pytest.raises(AttributeError):
                item.lyrics_language
        # make sure translation language is cleared
        with pytest.raises(AttributeError):
            item.lyrics_translation_language

    def test_imported_skips_auto_ignored_items(
        self, lyrics_plugin, monkeypatch
    ):
        lyrics_plugin.config["auto_ignore"].set("album:Greatest Hits")
        items = [
            Item(title="Old Song", album="Greatest Hits", genre="Rock"),
            Item(title="Come Together", album="Abbey Road", genre="Rock"),
        ]

        calls = []
        monkeypatch.setattr(
            lyrics_plugin,
            "add_item_lyrics",
            lambda current_item, write: calls.append(
                (current_item.title, write)
            ),
        )

        task = SimpleNamespace(imported_items=lambda: items)
        lyrics_plugin.imported(None, task)

        assert calls == [("Come Together", False)]


class LyricsBackendTest(LyricsPluginMixin):
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

    def test_backend_source(
        self, monkeypatch, lyrics_plugin, lyrics_page: LyricsPage
    ):
        """Test parsed lyrics from each of the configured lyrics pages."""
        monkeypatch.setattr(
            "beetsplug.lyrics.LyricsRequestHandler.create_session",
            lambda _: requests.Session(),
        )
        expected_lyrics = Lyrics(
            lyrics_page.lyrics,
            lyrics_page.backend,
            url=lyrics_page.url,
            language=lyrics_page.language,
        )

        actual_lyrics = lyrics_plugin.find_lyrics(
            Item(
                artist=lyrics_page.artist,
                title=lyrics_page.track_title,
                album="",
                length=186.0,
            )
        )
        assert actual_lyrics
        assert actual_lyrics.text == expected_lyrics.text
        assert actual_lyrics == expected_lyrics


class TestGoogleLyrics(LyricsBackendTest):
    """Test scraping heuristics on a fake html page."""

    @pytest.fixture(scope="class")
    def backend_name(self):
        return "google"

    @pytest.fixture
    def plugin_config(self):
        return {"google_API_key": "test"}

    @pytest.fixture(scope="class")
    def file_name(self):
        return "examplecom/beetssong"

    @pytest.fixture
    def search_item(self, url_title, url):
        return {"title": url_title, "link": url}

    @pytest.mark.parametrize("plugin_config", [{}])
    def test_disabled_without_api_key(self, lyrics_plugin):
        assert not lyrics_plugin.backends

    def test_mocked_source_ok(self, backend, lyrics_html):
        """Test that lyrics of the mocked page are correctly scraped"""
        result = backend.scrape(lyrics_html).lower()

        assert result
        assert PHRASE_BY_TITLE["Beets song"] in result

    @pytest.mark.parametrize(
        "url_title, expected_artist, expected_title",
        [
            ("Artist - beets song Lyrics", "Artist", "beets song"),
            ("www.azlyrics.com | Beats song by Artist", "Artist", "Beats song"),
            ("lyric.com | seets bong lyrics by Artist", "Artist", "seets bong"),
            ("foo", "", "foo"),
            ("Artist - Beets Song lyrics | AZLyrics", "Artist", "Beets Song"),
            ("Letra de Artist - Beets Song", "Artist", "Beets Song"),
            ("Letra de Artist - Beets ...", "Artist", "Beets"),
            ("Artist Beets Song", "Artist", "Beets Song"),
            ("BeetsSong - Artist", "Artist", "BeetsSong"),
            ("Artist - BeetsSong", "Artist", "BeetsSong"),
            ("Beets Song", "", "Beets Song"),
            ("Beets Song Artist", "Artist", "Beets Song"),
            (
                "BeetsSong (feat. Other & Another) - Artist",
                "Artist",
                "BeetsSong (feat. Other & Another)",
            ),
            (
                (
                    "Beets song lyrics by Artist - original song full text. "
                    "Official Beets song lyrics, 2024 version | LyricsMode.com"
                ),
                "Artist",
                "Beets song",
            ),
        ],
    )
    @pytest.mark.parametrize("url", ["http://doesntmatter.com"])
    def test_make_search_result(
        self, backend, search_item, expected_artist, expected_title
    ):
        result = backend.make_search_result("Artist", "Beets song", search_item)

        assert result.artist == expected_artist
        assert result.title == expected_title


class TestGeniusLyrics(LyricsBackendTest):
    @pytest.fixture(scope="class")
    def backend_name(self):
        return "genius"

    @pytest.mark.parametrize(
        "file_name, expected_line_count",
        [
            ("geniuscom/2pacalleyezonmelyrics", 131),
            ("geniuscom/Ttngchinchillalyrics", 29),
            ("geniuscom/sample", 0),  # see https://github.com/beetbox/beets/issues/3535
        ],
    )  # fmt: skip
    def test_scrape(self, backend, lyrics_html, expected_line_count):
        result = backend.scrape(lyrics_html) or ""

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
                "tekstowopl/piosenkabeethovenbeethovenpianosonata17tempestthe3rdmovement",
                False,
            ),
        ],
    )
    def test_scrape(self, backend, lyrics_html, expecting_lyrics):
        assert bool(backend.scrape(lyrics_html)) == expecting_lyrics


LYRICS_DURATION = 950


def lyrics_match(**overrides):
    return {
        "id": 1,
        "instrumental": False,
        "duration": LYRICS_DURATION,
        "syncedLyrics": "[00:00.00] synced",
        "plainLyrics": "plain",
        **overrides,
    }


class TestLRCLibLyrics(LyricsBackendTest):
    ITEM_DURATION = 999
    SYNCED = "[00:00.00] synced"

    @pytest.fixture(scope="class")
    def backend_name(self):
        return "lrclib"

    @pytest.fixture
    def fetch_lyrics(self, backend, requests_mock, response_data):
        requests_mock.get(backend.GET_URL, status_code=HTTPStatus.NOT_FOUND)
        requests_mock.get(backend.SEARCH_URL, json=response_data)

        return partial(backend.fetch, "la", "la", "la", self.ITEM_DURATION)

    @pytest.mark.parametrize("response_data", [[lyrics_match()]])
    @pytest.mark.parametrize(
        "plugin_config, expected_lyrics",
        [
            pytest.param({"synced": True}, SYNCED, id="pick-synced"),
            pytest.param({"synced": False}, "plain", id="pick-plain"),
        ],
    )
    def test_synced_config_option(
        self, backend_name, fetch_lyrics, expected_lyrics
    ):
        lyrics = fetch_lyrics()

        assert lyrics
        assert lyrics.text == expected_lyrics
        assert lyrics.backend == backend_name

    @pytest.mark.parametrize(
        "response_data, expected_lyrics",
        [
            pytest.param([], None, id="handle non-matching lyrics"),
            pytest.param([lyrics_match()], SYNCED, id="synced when available"),
            pytest.param(
                [lyrics_match(duration=1)], None, id="none: duration too short"
            ),
            pytest.param(
                [lyrics_match(instrumental=True)],
                "[Instrumental]",
                id="instrumental track",
            ),
            pytest.param(
                [lyrics_match(syncedLyrics=None)],
                "plain",
                id="plain by default",
            ),
            pytest.param(
                [
                    lyrics_match(
                        duration=ITEM_DURATION,
                        syncedLyrics=None,
                        plainLyrics="plain with closer duration",
                    ),
                    lyrics_match(syncedLyrics=SYNCED, plainLyrics="plain 2"),
                ],
                SYNCED,
                id="prefer synced lyrics even if plain duration is closer",
            ),
            pytest.param(
                [
                    lyrics_match(
                        duration=ITEM_DURATION,
                        syncedLyrics=None,
                        plainLyrics="valid plain",
                    ),
                    lyrics_match(
                        duration=1, syncedLyrics="synced with invalid duration"
                    ),
                ],
                "valid plain",
                id="ignore synced with invalid duration",
            ),
            pytest.param(
                [
                    lyrics_match(
                        duration=59, syncedLyrics="[01:00.00] invalid synced"
                    )
                ],
                None,
                id="ignore synced with a timestamp longer than duration",
            ),
            pytest.param(
                [lyrics_match(syncedLyrics=None), lyrics_match()],
                SYNCED,
                id="prefer match with synced lyrics",
            ),
        ],
    )
    @pytest.mark.parametrize("plugin_config", [{"synced": True}])
    def test_fetch_lyrics(self, fetch_lyrics, expected_lyrics):
        lyrics = fetch_lyrics()
        if expected_lyrics is None:
            assert not lyrics
        else:
            assert lyrics
            assert lyrics.text == expected_lyrics


class TestTidalLyrics(LyricsBackendTest):
    @pytest.fixture(scope="class")
    def backend_name(self):
        return "tidal"

    @staticmethod
    def search_doc(
        *,
        track_id="track-1",
        artist="Target Artist",
        title="Target Title",
        include_artist=True,
    ):
        included = [
            {
                "id": track_id,
                "type": "tracks",
                "attributes": {"title": title},
                "relationships": {
                    "artists": {"data": [{"id": "artist-1", "type": "artists"}]}
                },
            }
        ]
        if include_artist:
            included.append(
                {
                    "id": "artist-1",
                    "type": "artists",
                    "attributes": {"name": artist},
                }
            )

        return {
            "data": {
                "id": "search",
                "type": "searchResults",
                "attributes": {"trackingId": "tracking-id"},
                "relationships": {
                    "tracks": {"data": [{"id": track_id, "type": "tracks"}]}
                },
            },
            "included": included,
        }

    @staticmethod
    def lyrics_doc(
        *,
        track_id="track-1",
        lyric_id="lyric-1",
        text="plain lyrics",
        lrc_text="[00:00.00] synced lyrics",
        status="OK",
    ):
        attributes = {"text": text, "lrcText": lrc_text}
        if status is not None:
            attributes["technicalStatus"] = status

        return {
            "data": [
                {
                    "id": track_id,
                    "type": "tracks",
                    "relationships": {
                        "lyrics": {"data": [{"id": lyric_id, "type": "lyrics"}]}
                    },
                }
            ],
            "included": [
                {"id": lyric_id, "type": "lyrics", "attributes": attributes}
            ],
        }

    @pytest.fixture
    def tidal_api(self):
        return Mock(
            search_results=Mock(return_value=self.search_doc()),
            get_tracks=Mock(return_value=self.lyrics_doc()),
        )

    @pytest.fixture
    def fetch_lyrics(self, backend, monkeypatch, tidal_api):
        monkeypatch.setattr(backend, "api", tidal_api)
        monkeypatch.setattr(backend, "token_has_required_scopes", True)
        return partial(backend.fetch, "Target Artist", "Target Title", "", 0)

    @pytest.mark.parametrize(
        "plugin_config, expected_lyrics",
        [
            pytest.param({"synced": False}, "plain lyrics", id="plain"),
            pytest.param(
                {"synced": True}, "[00:00.00] synced lyrics", id="synced"
            ),
        ],
    )
    def test_synced_config_option(
        self, fetch_lyrics, expected_lyrics, backend_name
    ):
        actual = fetch_lyrics()

        assert actual
        assert actual.text == expected_lyrics
        assert actual.backend == backend_name
        assert actual.url == "https://tidal.com/browse/track/track-1"

    def test_uses_tidal_country_code(self, fetch_lyrics, tidal_api):
        fetch_lyrics()

        tidal_api.search_results.assert_called_once_with(
            "Target Artist Target Title",
            include=["tracks.artists"],
            country_code="US",
        )
        tidal_api.get_tracks.assert_called_once_with(
            ids=["track-1"], include=["lyrics"], country_code="US"
        )

    def test_fetches_matched_tracks_in_batch(self, fetch_lyrics, tidal_api):
        search_data = self.search_doc()
        search_data["data"]["relationships"]["tracks"]["data"].append(
            {"id": "track-2", "type": "tracks"}
        )
        search_data["included"].append(
            {
                "id": "track-2",
                "type": "tracks",
                "attributes": {"title": "Target Title"},
                "relationships": {
                    "artists": {"data": [{"id": "artist-1", "type": "artists"}]}
                },
            }
        )
        tidal_api.search_results.return_value = search_data
        tidal_api.get_tracks.return_value = {
            "data": [
                {
                    "id": "track-1",
                    "type": "tracks",
                    "relationships": {"lyrics": {"data": []}},
                },
                {
                    "id": "track-2",
                    "type": "tracks",
                    "relationships": {
                        "lyrics": {
                            "data": [{"id": "lyric-2", "type": "lyrics"}]
                        }
                    },
                },
            ],
            "included": [
                {
                    "id": "lyric-2",
                    "type": "lyrics",
                    "attributes": {
                        "technicalStatus": "OK",
                        "text": "second track lyrics",
                    },
                }
            ],
        }

        actual = fetch_lyrics()

        assert actual
        assert actual.text == "second track lyrics"
        assert actual.url == "https://tidal.com/browse/track/track-2"
        tidal_api.get_tracks.assert_called_once_with(
            ids=["track-1", "track-2"], include=["lyrics"], country_code="US"
        )

    def test_ignores_unrelated_search_included_items(
        self, fetch_lyrics, tidal_api
    ):
        search_data = self.search_doc()
        search_data["included"].append({"id": "album-1", "type": "albums"})
        tidal_api.search_results.return_value = search_data

        actual = fetch_lyrics()

        assert actual
        assert actual.text == "plain lyrics"

    def test_skips_search_without_tracks_relationship(
        self, fetch_lyrics, tidal_api
    ):
        search_data = self.search_doc()
        search_data["data"]["relationships"] = {}
        tidal_api.search_results.return_value = search_data

        assert fetch_lyrics() is None
        tidal_api.get_tracks.assert_not_called()

    def test_skips_search_result_missing_sideloaded_track(
        self, fetch_lyrics, tidal_api
    ):
        search_data = self.search_doc()
        search_data["included"] = [
            item for item in search_data["included"] if item["type"] != "tracks"
        ]
        tidal_api.search_results.return_value = search_data

        assert fetch_lyrics() is None
        tidal_api.get_tracks.assert_not_called()

    def test_skips_track_missing_from_batched_response(
        self, fetch_lyrics, tidal_api
    ):
        tidal_api.get_tracks.return_value = {"data": [], "included": []}

        assert fetch_lyrics() is None

    def test_skips_lyrics_missing_from_batched_response(
        self, fetch_lyrics, tidal_api
    ):
        tidal_api.get_tracks.return_value = {
            "data": [
                {
                    "id": "track-1",
                    "type": "tracks",
                    "relationships": {
                        "lyrics": {
                            "data": [{"id": "lyric-1", "type": "lyrics"}]
                        }
                    },
                }
            ],
            "included": [],
        }

        assert fetch_lyrics() is None

    @pytest.mark.parametrize(
        "search_data, lyrics_data",
        [
            pytest.param(
                search_doc(title="Different Title"),
                lyrics_doc(),
                id="skip-nonmatching-track",
            ),
            pytest.param(
                search_doc(),
                {
                    "data": [
                        {
                            "id": "track-1",
                            "type": "tracks",
                            "relationships": {"lyrics": {"data": []}},
                        }
                    ],
                    "included": [],
                },
                id="skip-track-without-lyrics",
            ),
            pytest.param(
                search_doc(),
                lyrics_doc(status="PROCESSING"),
                id="skip-unready-lyrics",
            ),
            pytest.param(
                search_doc(),
                lyrics_doc(status=None),
                id="skip-lyric-without-status",
            ),
            pytest.param(
                {"errors": [{"detail": "invalid token"}]},
                lyrics_doc(),
                id="skip-search-error-document",
            ),
            pytest.param(
                search_doc(),
                {"errors": [{"detail": "lyrics unavailable"}]},
                id="skip-lyrics-error-document",
            ),
        ],
    )
    def test_fetch_lyrics_none(
        self, fetch_lyrics, tidal_api, search_data, lyrics_data
    ):
        tidal_api.search_results.return_value = search_data
        tidal_api.get_tracks.return_value = lyrics_data

        assert fetch_lyrics() is None

    def test_warns_for_null_track_data(self, fetch_lyrics, tidal_api, caplog):
        tidal_api.get_tracks.return_value = {
            "data": None,
            "errors": [{"detail": "lyrics unavailable"}],
        }

        assert fetch_lyrics() is None
        assert "TIDAL track response did not include track data" in caplog.text

    def test_warns_for_missing_lyrics_data(
        self, fetch_lyrics, tidal_api, caplog
    ):
        tidal_api.get_tracks.return_value = {
            "data": [{"id": "track-1", "type": "tracks"}]
        }

        assert fetch_lyrics() is None
        assert "TIDAL track response did not include lyric data" in caplog.text

    def test_matches_by_title_when_artist_not_sideloaded(
        self, fetch_lyrics, tidal_api
    ):
        tidal_api.search_results.return_value = self.search_doc(
            include_artist=False
        )

        actual = fetch_lyrics()

        assert actual
        assert actual.text == "plain lyrics"

    def test_logs_near_miss(self, backend, caplog):
        track = self.search_doc(title="Target Tale")["included"][0]

        with caplog.at_level(logging.DEBUG):
            assert not backend.check_match(
                "Target Artist", "Target Title", track, "Target Artist"
            )

        assert (
            "Tidal: (Target Artist, Target Tale) does not match" in caplog.text
        )
        assert "but dist was close: 0.18" in caplog.text

    def test_far_miss_does_not_log_debug(self, backend, caplog):
        track = self.search_doc(artist="Other Artist", title="Unrelated Song")[
            "included"
        ][0]

        with caplog.at_level(logging.DEBUG):
            assert not backend.check_match(
                "Target Artist", "Target Title", track, "Other Artist"
            )

        assert "does not match" not in caplog.text

    def test_matches_versioned_track_title(self, backend):
        track = self.search_doc()["included"][0]
        track["attributes"]["version"] = "Remastered"

        assert backend.track_title(track) == "Target Title (Remastered)"

    def test_matches_by_title_when_artist_relationship_missing(
        self, fetch_lyrics, tidal_api
    ):
        search_data = self.search_doc(include_artist=False)
        del search_data["included"][0]["relationships"]
        tidal_api.search_results.return_value = search_data

        actual = fetch_lyrics()

        assert actual
        assert actual.text == "plain lyrics"

    @pytest.mark.parametrize("plugin_config", [{"synced": False}])
    def test_no_lrc_fallback_when_unsynced(self, fetch_lyrics, tidal_api):
        tidal_api.get_tracks.return_value = self.lyrics_doc(
            text=None, lrc_text="[00:00.00] synced lyrics"
        )

        assert fetch_lyrics() is None

    def test_skips_api_without_required_token_scopes(
        self, backend, monkeypatch, tidal_api
    ):
        monkeypatch.setattr(backend, "api", tidal_api)
        monkeypatch.setattr(backend, "token_has_required_scopes", False)

        assert backend.fetch("Target Artist", "Target Title", "", 0) is None
        tidal_api.search_results.assert_not_called()
        tidal_api.get_tracks.assert_not_called()

    def test_rejects_token_missing_required_scopes(self, backend, tmp_path):
        tokenfile = tmp_path / "tidal_token.json"
        tokenfile.write_text('{"scope": "search.read"}')
        backend.config["tidal"]["tokenfile"].set(str(tokenfile))

        assert not backend.token_has_required_scopes

    def test_rejects_invalid_token_file(self, backend, tmp_path: Path, caplog):
        tokenfile = tmp_path / "tidal_token.json"
        tokenfile.write_text("{")
        backend.config["tidal"]["tokenfile"].set(str(tokenfile))

        assert not backend.token_has_required_scopes
        assert "Could not decode TIDAL token file" in caplog.text

    def test_accepts_token_with_required_scopes(self, backend, tmp_path):
        tokenfile = tmp_path / "tidal_token.json"
        tokenfile.write_text('{"scope": "search.read user.read"}')
        backend.config["tidal"]["tokenfile"].set(str(tokenfile))

        assert backend.token_has_required_scopes

    def test_scope_set_ignores_unknown_config(self, backend):
        assert backend.scope_set(42) == set()

    @pytest.mark.parametrize(
        "plugin_config", [{"tidal": {"scope": ["search.read", "user.read"]}}]
    )
    def test_accepts_scope_list_config(self, backend):
        assert backend.required_scopes == {"search.read", "user.read"}
        assert backend.scope == "search.read user.read"
        assert backend.api.scope == "search.read user.read"


@pytest.mark.requires_import("langdetect")
class TestTranslation:
    @pytest.fixture(autouse=True)
    def _patch_bing(self, requests_mock):
        def callback(request, _):
            if b"Refrain" in request.body:
                translations = (
                    ""
                    " | [Refrain : Doja Cat]"
                    " | Difficile pour moi de te laisser partir (Te laisser partir, te laisser partir)"  # noqa: E501
                    " | Mon corps ne me laissait pas le cacher (Cachez-le)"
                    " | [Chorus]"
                    " | Quoi qu’il arrive, je ne plierais pas (Ne plierait pas, ne plierais pas)"  # noqa: E501
                    " | Chevauchant à travers le tonnerre, la foudre"
                )
            elif b"00:00.00" in request.body:
                translations = (
                    ""
                    " | [00:00.00] Quelques paroles synchronisées"
                    " | [00:01.00] Quelques paroles plus synchronisées"
                )
            else:
                translations = (
                    ""
                    " | Quelques paroles synchronisées"
                    " | Quelques paroles plus synchronisées"
                )

            return [
                {
                    "detectedLanguage": {"language": "en", "score": 1.0},
                    "translations": [{"text": translations, "to": "fr"}],
                }
            ]

        requests_mock.post(lyrics.Translator.TRANSLATE_URL, json=callback)

    @pytest.mark.parametrize(
        "new_lyrics, old_lyrics, expected",
        [
            pytest.param(
                """
                [Refrain: Doja Cat]
                Hard for me to let you go (Let you go, let you go)
                My body wouldn't let me hide it (Hide it)
                [Chorus]
                No matter what, I wouldn't fold (Wouldn't fold, wouldn't fold)
                Ridin' through the thunder, lightnin'""",
                Lyrics(""),
                """
                [Refrain: Doja Cat] / [Refrain : Doja Cat]
                Hard for me to let you go (Let you go, let you go) / Difficile pour moi de te laisser partir (Te laisser partir, te laisser partir)
                My body wouldn't let me hide it (Hide it) / Mon corps ne me laissait pas le cacher (Cachez-le)
                [Chorus]
                No matter what, I wouldn't fold (Wouldn't fold, wouldn't fold) / Quoi qu’il arrive, je ne plierais pas (Ne plierait pas, ne plierais pas)
                Ridin' through the thunder, lightnin' / Chevauchant à travers le tonnerre, la foudre""",  # noqa: E501
                id="plain",
            ),
            pytest.param(
                """
                [00:00.00] Some synced lyrics
                [00:00.50]
                [00:01.00] Some more synced lyrics
                """,
                Lyrics(""),
                """
                [00:00.00] Some synced lyrics / Quelques paroles synchronisées
                [00:00.50]
                [00:01.00] Some more synced lyrics / Quelques paroles plus synchronisées""",  # noqa: E501
                id="synced",
            ),
            pytest.param(
                "Quelques paroles",
                Lyrics(""),
                "Quelques paroles",
                id="already in the target language",
            ),
            pytest.param(
                "Some lyrics",
                Lyrics(
                    "Some lyrics / Some translation",
                    language="EN",
                    translation_language="FR",
                ),
                "Some lyrics / Some translation",
                id="already translated",
            ),
        ],
    )
    def test_translate(self, new_lyrics, old_lyrics, expected):
        plugin = lyrics.LyricsPlugin()
        bing = lyrics.Translator(plugin._log, "123", "FR", ["EN"])

        assert bing.translate(
            Lyrics(textwrap.dedent(new_lyrics)), old_lyrics
        ).full_text == textwrap.dedent(expected)


class TestRestFiles:
    @pytest.fixture
    def rest_dir(self, tmp_path):
        return tmp_path

    @pytest.fixture
    def rest_files(self, rest_dir):
        return lyrics.RestFiles(rest_dir)

    def test_write(self, rest_dir: Path, rest_files):
        items = [
            Item(albumartist=aa, album=a, title=t, lyrics=lyr)
            for aa, a, t, lyr in [
                ("Artist One", "Album One", "Song One", "Lyrics One"),
                ("Artist One", "Album One", "Song Two", "Lyrics Two"),
                ("Artist Two", "Album Two", "Song Three", "Lyrics Three"),
            ]
        ]

        rest_files.write(items)

        assert (rest_dir / "index.rst").exists()
        assert (rest_dir / "conf.py").exists()

        artist_one_file = rest_dir / "artists" / "artist-one.rst"
        artist_two_file = rest_dir / "artists" / "artist-two.rst"
        assert artist_one_file.exists()
        assert artist_two_file.exists()

        c = artist_one_file.read_text()
        assert (
            c.index("Artist One")
            < c.index("Album One")
            < c.index("Song One")
            < c.index("Lyrics One")
            < c.index("Song Two")
            < c.index("Lyrics Two")
        )

        c = artist_two_file.read_text()
        assert (
            c.index("Artist Two")
            < c.index("Album Two")
            < c.index("Song Three")
            < c.index("Lyrics Three")
        )


class TestLyricsSyltProperty:
    """Unit tests for the Lyrics.sylt timestamp-to-millisecond converter."""

    @pytest.mark.parametrize(
        "lrc_text, expected_sylt",
        [
            pytest.param(
                "[00:01.00] line one\n[00:02.50] line two",
                [("line one", 1000), ("line two", 2500)],
                id="basic-lrc-to-ms",
            ),
            pytest.param(
                "[01:30.50] one and a half minutes",
                [("one and a half minutes", 90500)],
                id="over-one-minute",
            ),
            pytest.param(
                "plain lyrics without timestamps",
                [],
                id="plain-lyrics-have-no-sylt",
            ),
            pytest.param(
                "[00:00.00] timed\nuntimed line\n[00:05.00] timed again",
                [("timed", 0), ("timed again", 5000)],
                id="untimed-lines-omitted",
            ),
            pytest.param(
                "[00:00.00] \n[00:01.00] second",
                [("", 0), ("second", 1000)],
                id="empty-text-line-included",
            ),
        ],
    )
    def test_sylt(self, lrc_text, expected_sylt):
        assert Lyrics(lrc_text).sylt == expected_sylt


class TestSyncedLyricsWrite(LyricsPluginMixin):
    """Tests that add_item_lyrics passes the correct synced_lyrics tag."""

    SYNCED_LRC = "[00:01.00] hello\n[00:02.00] world"

    @pytest.fixture
    def backend_name(self):
        return "lrclib"

    def test_sylt_data_passed_for_synced_lyrics(
        self, monkeypatch, helper, lyrics_plugin
    ):
        monkeypatch.setattr(
            lyrics_plugin, "find_lyrics", lambda _: Lyrics(self.SYNCED_LRC)
        )
        item = helper.create_item(id=1, lyrics="")
        calls = []
        monkeypatch.setattr(
            type(item), "try_write", lambda self, **kw: calls.append(kw) or True
        )

        lyrics_plugin.add_item_lyrics(item, write=True)

        assert calls == [
            {"tags": {"synced_lyrics": [("hello", 1000), ("world", 2000)]}}
        ]

    def test_lrc_text_kept_in_db_for_synced(
        self, monkeypatch, helper, lyrics_plugin
    ):
        """LRC text is stored in the DB so keep_synced detection still works."""
        monkeypatch.setattr(
            lyrics_plugin, "find_lyrics", lambda _: Lyrics(self.SYNCED_LRC)
        )
        item = helper.create_item(id=1, lyrics="")
        monkeypatch.setattr(type(item), "try_write", lambda self, **kw: True)

        lyrics_plugin.add_item_lyrics(item, write=True)

        assert item.lyrics == self.SYNCED_LRC

    def test_sylt_cleared_for_plain_lyrics(
        self, monkeypatch, helper, lyrics_plugin
    ):
        monkeypatch.setattr(
            lyrics_plugin, "find_lyrics", lambda _: Lyrics("plain lyrics")
        )
        item = helper.create_item(id=1, lyrics="")
        calls = []
        monkeypatch.setattr(
            type(item), "try_write", lambda self, **kw: calls.append(kw) or True
        )

        lyrics_plugin.add_item_lyrics(item, write=True)

        assert calls == [{"tags": {"synced_lyrics": None}}]

    def test_sylt_and_uslt_written_to_mp3(
        self, monkeypatch, helper, lyrics_plugin
    ):
        """Integration: SYLT + plain USLT are written to a real MP3 file."""
        import mutagen

        monkeypatch.setattr(
            lyrics_plugin, "find_lyrics", lambda _: Lyrics(self.SYNCED_LRC)
        )
        item = helper.add_item_fixture(format="MP3", lyrics="")

        lyrics_plugin.add_item_lyrics(item, write=True)

        f = mutagen.File(item.path)
        assert f.tags.getall("SYLT"), "SYLT frame should be present"
        assert f.tags["SYLT::XXX"].text == [("hello", 1000), ("world", 2000)]
        assert f.tags.getall("USLT"), "USLT frame should be present"
        # USLT retains the full LRC text (with timestamps) so players that
        # parse LRC in USLT, and non-ID3 formats, continue to work.
        assert f.tags["USLT::XXX"].text == self.SYNCED_LRC
