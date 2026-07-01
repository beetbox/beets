"""Tests for discogs plugin."""

from typing import Any

import pytest
from discogs_client import Client, Release

from beets import config
from beets.library import Item
from beets.test.helper import TestHelper
from beetsplug.discogs import ArtistState, DiscogsPlugin

_p = pytest.param


def _artist(name: str, **kwargs):
    return {
        "id": 1,
        "name": name,
        "join": "",
        "role": "",
        "anv": "",
        "tracks": "",
        "resource_url": "",
    } | kwargs


def _track(title: str, position: str = "", duration: str = "", **kwargs):
    return {
        "title": title,
        "position": position,
        "duration": duration,
        "type_": "track",
    } | kwargs


def get_release(data: dict[str, Any]) -> Release:
    return Release(Client("doesn't matter"), data)


@pytest.fixture(autouse=True)
def _patch_discogs_setup(monkeypatch):
    """Autouse fixture to patch DiscogsPlugin.setup for each test."""
    monkeypatch.setattr(
        "beetsplug.discogs.DiscogsPlugin.setup", lambda *_: None
    )


class DiscogsTestMixin:
    def _make_release(self, tracks=None):
        """Return discogs_client.Release.

        The returned object is incomplete, including just the fields required
        for tests in this module.
        """
        data = {
            "id": 11111111,
            "uri": "https://www.discogs.com/release/111111111",
            "title": "ALBUM TITLE",
            "year": 3001,
            "artists": [_artist("ARTIST NAME", join=",")],
            "formats": [
                {
                    "descriptions": ["FORMAT DESC 1", "FORMAT DESC 2"],
                    "name": "FORMAT",
                    "qty": 1,
                }
            ],
            # genres and styles are reversed in Discogs
            "genres": ["STYLE1", "STYLE2"],
            "styles": ["GENRE1", "GENRE2"],
            "labels": [{"name": "LABEL NAME", "catno": "CATALOG NUMBER"}],
            "tracklist": tracks or [],
        }

        return get_release(data)

    def _make_release_from_positions(self, positions):
        """Return discogs_client.Release with tracks at the given positions."""
        tracks = [
            _track(f"TITLE{i}", position)
            for (i, position) in enumerate(positions, start=1)
        ]
        return self._make_release(tracks)


class TestDGAlbumInfo(DiscogsTestMixin, TestHelper):
    def test_parse_media_for_tracks(self):
        tracks = [
            _track("TITLE ONE", "1", "01:01"),
            _track("TITLE TWO", "2", "02:02"),
        ]
        release = self._make_release(tracks=tracks)

        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks
        assert d.media == "FORMAT"
        assert t[0].media == d.media
        assert t[1].media == d.media

    def test_parse_medium_numbers_single_medium(self):
        release = self._make_release_from_positions(["1", "2"])
        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks

        assert d.mediums == 1
        assert t[0].medium == 1
        assert t[0].medium_total == 2
        assert t[1].medium == 1
        assert t[0].medium_total == 2

    def test_parse_medium_numbers_two_mediums(self):
        release = self._make_release_from_positions(["1-1", "2-1"])
        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks

        assert d.mediums == 2
        assert t[0].medium == 1
        assert t[0].medium_total == 1
        assert t[1].medium == 2
        assert t[1].medium_total == 1

    def test_parse_medium_numbers_two_mediums_two_sided(self):
        release = self._make_release_from_positions(["A1", "B1", "C1"])
        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks

        assert d.mediums == 2
        assert t[0].medium == 1
        assert t[0].medium_total == 2
        assert t[0].medium_index == 1
        assert t[1].medium == 1
        assert t[1].medium_total == 2
        assert t[1].medium_index == 2
        assert t[2].medium == 2
        assert t[2].medium_total == 1
        assert t[2].medium_index == 1

    def test_parse_track_indices(self):
        release = self._make_release_from_positions(["1", "2"])
        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks

        assert t[0].medium_index == 1
        assert t[0].index == 1
        assert t[0].medium_total == 2
        assert t[1].medium_index == 2
        assert t[1].index == 2
        assert t[1].medium_total == 2

    def test_parse_track_indices_several_media(self):
        release = self._make_release_from_positions(
            ["1-1", "1-2", "2-1", "3-1"]
        )
        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks

        assert d.mediums == 3
        assert t[0].medium_index == 1
        assert t[0].index == 1
        assert t[0].medium_total == 2
        assert t[1].medium_index == 2
        assert t[1].index == 2
        assert t[1].medium_total == 2
        assert t[2].medium_index == 1
        assert t[2].index == 3
        assert t[2].medium_total == 1
        assert t[3].medium_index == 1
        assert t[3].index == 4
        assert t[3].medium_total == 1

    def test_parse_minimal_release(self):
        """Test parsing of a release with the minimal amount of information."""
        data = {
            "id": 123,
            "uri": "https://www.discogs.com/release/123456-something",
            "tracklist": [_track("A", "1", "01:01")],
            "artists": [_artist("ARTIST NAME", id=321)],
            "title": "TITLE",
        }
        release = get_release(data)
        d = DiscogsPlugin().get_album_info(release)
        assert d.artist == "ARTIST NAME"
        assert d.album == "TITLE"
        assert len(d.tracks) == 1

    def test_default_genre_style_settings(self):
        """Test genre default settings, genres to genre, styles to style"""
        release = self._make_release_from_positions(["1", "2"])

        d = DiscogsPlugin().get_album_info(release)
        assert d.style == "STYLE1, STYLE2"
        assert d.genres == ["GENRE1", "GENRE2"]

    def test_append_style_to_genre(self):
        """Test appending style to genre if config enabled"""
        config["discogs"]["append_style_genre"] = True
        release = self._make_release_from_positions(["1", "2"])

        d = DiscogsPlugin().get_album_info(release)
        assert d.style == "STYLE1, STYLE2"
        assert d.genres == ["GENRE1", "GENRE2", "STYLE1", "STYLE2"]

    def test_append_style_to_genre_no_styles(self):
        """Test nothing appended to genre if style is empty"""
        config["discogs"]["append_style_genre"] = True
        release = self._make_release_from_positions(["1", "2"])
        release.data["genres"] = []

        d = DiscogsPlugin().get_album_info(release)
        assert d.style is None
        assert d.genres == ["GENRE1", "GENRE2"]

    def test_strip_disambiguation(self):
        """Test removing disambiguation from all disambiguated fields."""
        data = {
            "id": 123,
            "uri": "https://www.discogs.com/release/123456-something",
            "tracklist": [
                {
                    "title": "track",
                    "position": "A",
                    "type_": "track",
                    "duration": "5:44",
                    "artists": [_artist("TEST ARTIST (5)", id=11146)],
                }
            ],
            "artists": [
                _artist("ARTIST NAME (2)", id=321, join="&"),
                _artist("OTHER ARTIST (5)", id=322),
            ],
            "title": "title",
            "labels": [{"name": "LABEL NAME (5)", "catno": "catalog number"}],
        }
        d = DiscogsPlugin().get_album_info(get_release(data))
        assert d.artist == "ARTIST NAME & OTHER ARTIST"
        assert d.artists == ["ARTIST NAME", "OTHER ARTIST"]
        assert d.artists_ids == ["321", "322"]
        assert d.tracks[0].artist == "TEST ARTIST"
        assert d.tracks[0].artists == ["TEST ARTIST"]
        assert d.tracks[0].artist_id == "11146"
        assert d.tracks[0].artists_ids == ["11146"]
        assert d.label == "LABEL NAME"

    def test_strip_disambiguation_false(self):
        """Test disabling disambiguation removal from all disambiguated fields."""
        config["discogs"]["strip_disambiguation"] = False
        data = {
            "id": 123,
            "uri": "https://www.discogs.com/release/123456-something",
            "tracklist": [
                {
                    "title": "track",
                    "position": "A",
                    "type_": "track",
                    "duration": "5:44",
                    "artists": [_artist("TEST ARTIST (5)", id=11146)],
                }
            ],
            "artists": [
                _artist("ARTIST NAME (2)", id=321, join="&"),
                _artist("OTHER ARTIST (5)", id=322),
            ],
            "title": "title",
            "labels": [{"name": "LABEL NAME (5)", "catno": "catalog number"}],
        }
        d = DiscogsPlugin().get_album_info(get_release(data))
        assert d.artist == "ARTIST NAME (2) & OTHER ARTIST (5)"
        assert d.artists == ["ARTIST NAME (2)", "OTHER ARTIST (5)"]
        assert d.tracks[0].artist == "TEST ARTIST (5)"
        assert d.tracks[0].artists == ["TEST ARTIST (5)"]
        assert d.label == "LABEL NAME (5)"
        config["discogs"]["strip_disambiguation"] = True


class TestTracklist(DiscogsTestMixin):
    @pytest.fixture
    def plugin(self):
        return DiscogsPlugin()

    @pytest.mark.parametrize(
        "positions,expected_mediums,expected_tracks",
        [
            _p(["1", "2", "3"], 1, 3, id="without-sides"),
            _p(["A1", "A2", "B1", "B2"], 1, 4, id="with-sides"),
            _p(["A1", "A2", "B1", "C1"], 2, 4, id="multiple-lp"),
            _p(["1-1", "1-2", "2-1", "3-1"], 3, 4, id="multiple-cd"),
            _p(["I", "II", "III", "IV"], 1, 4, id="non-standard"),
            _p(["1", "2.1", "2.2", "3"], 1, 3, id="subtracks-dot"),
            _p(["A1", "A2.1", "A2.2", "A3"], 1, 3, id="subtracks-dot-with-sides"),
            _p(["A1", "A2a", "A2b", "A3"], 1, 3, id="subtracks-letter"),
            _p(["A1", "A2.a", "A2.b", "A3"], 1, 3, id="subtracks-letter-with-dot"),
            _p(["1", "2", "Video 1"], 2, 3, id="subtracks-extra-material"),
        ],
    )  # fmt: skip
    def test_parse_tracklist_positions(
        self, plugin, positions, expected_mediums, expected_tracks
    ):
        release = self._make_release_from_positions(positions)
        d = plugin.get_album_info(release)

        assert d.mediums == expected_mediums
        assert len(d.tracks) == expected_tracks

    @pytest.mark.parametrize(
        "tracks,expected_mediums,expected_tracks",
        [
            _p(
                [
                    _track("MEDIUM TITLE"),
                    _track("TRACK GROUP TITLE"),
                    _track("TITLE ONE", "1.1"),
                    _track("TITLE TWO", "1.2"),
                ],
                1,
                [("TRACK GROUP TITLE", "MEDIUM TITLE")],
                id="flat-logical-subtracks",
            ),
            _p(
                [
                    _track("TITLE ONE", "1"),
                    _track(
                        "TRACK GROUP TITLE",
                        sub_tracks=[
                            _track("SUBTITLE ONE", "2.1", "01:01"),
                            _track("SUBTITLE TWO", "2.2", "02:02"),
                        ],
                    ),
                    _track("TITLE THREE", "3"),
                ],
                1,
                [
                    ("TITLE ONE", None),
                    ("TRACK GROUP TITLE", None),
                    ("TITLE THREE", None),
                ],
                id="nested-logical-subtracks",
            ),
            _p(
                [
                    _track("TITLE ONE", "1"),
                    _track(
                        "TRACK GROUP TITLE",
                        sub_tracks=[
                            _track("SUBTITLE ONE", "2", "01:01"),
                            _track("SUBTITLE TWO", "3", "02:02"),
                        ],
                    ),
                    _track("TITLE FOUR", "4"),
                ],
                1,
                [
                    ("TITLE ONE", None),
                    ("SUBTITLE ONE", None),
                    ("SUBTITLE TWO", None),
                    ("TITLE FOUR", None),
                ],
                id="nested-physical-subtracks",
            ),
            _p(
                [
                    _track("MEDIUM TITLE CD1"),
                    _track("TITLE ONE", "1-1"),
                    _track("TITLE TWO", "1-2"),
                    _track("MEDIUM TITLE CD2"),
                    _track("TITLE THREE", "2-1"),
                ],
                2,
                [
                    ("TITLE ONE", "MEDIUM TITLE CD1"),
                    ("TITLE TWO", "MEDIUM TITLE CD1"),
                    ("TITLE THREE", "MEDIUM TITLE CD2"),
                ],
                id="medium-titles",
            ),
        ],
    )  # fmt: skip
    def test_parse_tracklist_index_tracks(
        self, plugin, tracks, expected_mediums, expected_tracks
    ):
        release = self._make_release(tracks)
        album = plugin.get_album_info(release)

        assert album.mediums == expected_mediums
        assert [(t.title, t.disctitle) for t in album.tracks] == expected_tracks


class TestDGSearchQuery(TestHelper):
    def test_default_search_filters_without_extra_tags(self):
        """Discogs search uses only the type filter when no extra_tags are set."""
        plugin = DiscogsPlugin()
        items = [Item()]

        query, filters = plugin.get_search_query_with_filters(
            "album", items, "Artist", "Album", False
        )

        assert "Album" in query
        assert filters == {"type": "release"}

    def test_extra_tags_populate_discogs_filters(self):
        """Configured extra_tags should populate Discogs search filters."""
        plugin = DiscogsPlugin()
        plugin.config["extra_tags"] = ["label", "catalognum"]

        items = [
            Item(catalognum="ABC 123", label="abc"),
            Item(catalognum="ABC 123", label="abc"),
            Item(catalognum="ABC 123", label="def"),
        ]

        _query, filters = plugin.get_search_query_with_filters(
            "album", items, "Artist", "Album", False
        )

        assert filters["type"] == "release"
        assert filters["label"] == "abc"
        # Catalog number should have whitespace removed.
        assert filters["catno"] == "ABC123"
        config["discogs"]["extra_tags"] = []


class TestAnv:
    @pytest.fixture
    def album_info(self, monkeypatch, anv_config):
        monkeypatch.setattr(
            "beetsplug.discogs.DiscogsPlugin.setup", lambda _: None
        )
        data = {
            "id": 123,
            "uri": "https://www.discogs.com/release/123456-something",
            "tracklist": [
                {
                    "title": "track",
                    "position": "A",
                    "type_": "track",
                    "duration": "5:44",
                    "artists": [
                        _artist("ARTIST", id=11146, anv="ART", join="Feat."),
                        _artist("PERFORMER", id=787),
                    ],
                    "extraartists": [
                        _artist("PERFORMER", id=787, role="Featuring")
                    ],
                }
            ],
            "artists": [
                _artist("DRUMMER", id=445, anv="DRUM", join=", "),
                _artist("ARTIST (4)", id=321, anv="ARTY", join="&"),
                _artist("SOLOIST", id=446, anv="SOLO"),
            ],
            "title": "title",
        }
        release = get_release(data)
        plugin = DiscogsPlugin()
        plugin.config["anv"].set(
            {"artist": False, "album_artist": False, "artist_credit": False}
            | anv_config
        )
        return plugin.get_album_info(release)

    @staticmethod
    def _assert_fields(obj, expected):
        for field, value in expected.items():
            assert getattr(obj, field) == value

    @pytest.mark.parametrize(
        "anv_config,expected_track_fields",
        [
            (
                {"artist": False},
                {
                    "artist": "ARTIST Feat. PERFORMER",
                    "artists": ["ARTIST", "PERFORMER"],
                },
            ),
            (
                {"artist": True},
                {
                    "artist": "ART Feat. PERFORMER",
                    "artists": ["ART", "PERFORMER"],
                },
            ),
        ],
    )
    def test_track_artist_fields(self, album_info, expected_track_fields):
        self._assert_fields(album_info.tracks[0], expected_track_fields)

    @pytest.mark.parametrize(
        "anv_config,expected_album_fields,expected_track_fields",
        [
            (
                {"artist_credit": False},
                {
                    "artist_credit": "DRUMMER, ARTIST & SOLOIST",
                    "artists_credit": ["DRUMMER", "ARTIST", "SOLOIST"],
                },
                {
                    "artist_credit": "ARTIST Feat. PERFORMER",
                    "artists_credit": ["ARTIST", "PERFORMER"],
                },
            ),
            (
                {"artist_credit": True},
                {
                    "artist_credit": "DRUM, ARTY & SOLO",
                    "artists_credit": ["DRUM", "ARTY", "SOLO"],
                },
                {
                    "artist_credit": "ART Feat. PERFORMER",
                    "artists_credit": ["ART", "PERFORMER"],
                },
            ),
        ],
    )
    def test_artist_credit_fields(
        self, album_info, expected_album_fields, expected_track_fields
    ):
        self._assert_fields(album_info, expected_album_fields)
        self._assert_fields(album_info.tracks[0], expected_track_fields)

    @pytest.mark.parametrize(
        "anv_config,expected_album_fields",
        [
            (
                {"album_artist": False},
                {
                    "artist": "DRUMMER, ARTIST & SOLOIST",
                    "artists": ["DRUMMER", "ARTIST", "SOLOIST"],
                },
            ),
            (
                {"album_artist": True},
                {
                    "artist": "DRUM, ARTY & SOLO",
                    "artists": ["DRUM", "ARTY", "SOLO"],
                },
            ),
        ],
    )
    def test_album_artist_fields(self, album_info, expected_album_fields):
        self._assert_fields(album_info, expected_album_fields)


def test_anv_album_artist():
    """Test using artist name variations when the album artist
    is the same as the track artist, but only the track artist
    should use the artist name variation."""
    data = {
        "id": 123,
        "uri": "https://www.discogs.com/release/123456-something",
        "tracklist": [
            {
                "title": "track",
                "position": "A",
                "type_": "track",
                "duration": "5:44",
            }
        ],
        "artists": [_artist("ARTIST (4)", id=321, anv="VARIATION")],
        "title": "title",
    }
    release = get_release(data)
    config["discogs"]["anv"]["album_artist"] = False
    config["discogs"]["anv"]["artist"] = True
    config["discogs"]["anv"]["artist_credit"] = False
    r = DiscogsPlugin().get_album_info(release)
    assert r.artist == "ARTIST"
    assert r.artists == ["ARTIST"]
    assert r.artist_credit == "ARTIST"
    assert r.artist_id == "321"
    assert r.artists_credit == ["ARTIST"]
    assert r.tracks[0].artist == "VARIATION"
    assert r.tracks[0].artists == ["VARIATION"]
    assert r.tracks[0].artist_credit == "ARTIST"
    assert r.tracks[0].artists_credit == ["ARTIST"]


def test_parse_featured_artists():
    """Tests the plugins ability to parse a featured artist.
    Ignores artists that are not listed as featured."""
    track = {
        "type_": "track",
        "title": "track",
        "position": "1",
        "duration": "5:00",
        "artists": [
            _artist("NEW ARTIST", id=11146, join="&"),
            _artist("VOCALIST", id=344, join="feat."),
        ],
        "extraartists": [
            _artist("SOLOIST", id=3, role="Featuring"),
            _artist("PERFORMER (1)", id=5, role="Other Role, Featuring"),
            _artist("RANDOM", id=8, role="Written-By"),
            _artist("MUSICIAN", id=10, role="Featuring [Uncredited]"),
        ],
    }

    plugin = DiscogsPlugin()
    artistinfo = ArtistState.from_config(plugin.config, [_artist("ARTIST")])
    t, _, _ = plugin.get_track_info(track, 1, 1, artistinfo)
    assert (
        t.artist == "NEW ARTIST & VOCALIST feat. SOLOIST, PERFORMER, MUSICIAN"
    )
    assert t.artists == [
        "NEW ARTIST",
        "VOCALIST",
        "SOLOIST",
        "PERFORMER",
        "MUSICIAN",
    ]
    assert t.artists_ids == ["11146", "344", "3", "5", "10"]
    assert t.composers == ["RANDOM"]


def test_parse_extraartist_roles():
    plugin = DiscogsPlugin()
    artistinfo = ArtistState.from_config(plugin.config, [_artist("ARTIST")])
    track = {
        "type_": "track",
        "title": "track",
        "position": "1",
        "duration": "5:00",
        "artists": [_artist("TRACK ARTIST", id=11)],
        "extraartists": [
            _artist("LYRICIST", id=2, role="Lyrics By"),
            _artist("ARRANGER", id=3, role="Arranged By"),
            _artist("REMIXER", id=5, role="Remixed By"),
            _artist("COMPOSER", id=6, role="Written-By"),
        ],
    }

    t, _, _ = plugin.get_track_info(track, 1, 1, artistinfo)

    assert t.artist == "TRACK ARTIST"
    assert t.artists == ["TRACK ARTIST"]
    assert t.lyricists == ["LYRICIST"]
    assert t.arrangers == ["ARRANGER"]
    assert t.remixers == ["REMIXER"]
    assert t.composers == ["COMPOSER"]


@pytest.mark.parametrize(
    "formats, expected_media, expected_albumtype",
    [
        (None, None, None),
        (
            [
                {
                    "descriptions": ['7"', "Single", "45 RPM"],
                    "name": "Vinyl",
                    "qty": 1,
                }
            ],
            "Vinyl",
            '7", Single, 45 RPM',
        ),
    ],
)
def test_get_media_and_albumtype(formats, expected_media, expected_albumtype):
    result = DiscogsPlugin.get_media_and_albumtype(formats)

    assert result == (expected_media, expected_albumtype)


def test_va_buildartistinfo():
    config["va_name"] = "VARIOUS ARTISTS"
    expected_info = {
        "artist": "VARIOUS ARTISTS",
        "artist_id": "1",
        "artists": ["VARIOUS ARTISTS"],
        "artists_ids": ["1"],
        "artist_credit": "VARIOUS ARTISTS",
        "artists_credit": ["VARIOUS ARTISTS"],
        "arrangers": None,
        "composers": None,
        "remixers": None,
        "lyricists": None,
    }

    assert (
        ArtistState.from_config(
            DiscogsPlugin().config, [_artist("Various")]
        ).info
        == expected_info
    )


@pytest.mark.parametrize(
    "position, medium, index, subindex",
    [
        ("1", None, "1", None),
        ("A12", "A", "12", None),
        ("12-34", "12-", "34", None),
        ("CD1-1", "CD1-", "1", None),
        ("1.12", None, "1", "12"),
        ("12.a", None, "12", "A"),
        ("12.34", None, "12", "34"),
        ("1ab", None, "1", "AB"),
        # Non-standard
        ("IV", "IV", None, None),
    ],
)
def test_get_track_index(position, medium, index, subindex):
    assert DiscogsPlugin.get_track_index(position) == (medium, index, subindex)
