# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Tests for discogs plugin."""

from unittest.mock import Mock, patch

import pytest

from beets import config
from beets.library import Item
from beets.test._common import Bag
from beets.test.helper import BeetsTestCase, capture_log
from beetsplug.discogs import ArtistState, DiscogsPlugin


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


@patch("beetsplug.discogs.DiscogsPlugin.setup", Mock())
class DGAlbumInfoTest(BeetsTestCase):
    def _make_release(self, tracks=None):
        """Returns a Bag that mimics a discogs_client.Release. The list
        of elements on the returned Bag is incomplete, including just
        those required for the tests on this class."""
        data = {
            "id": "ALBUM ID",
            "uri": "https://www.discogs.com/release/release/13633721",
            "title": "ALBUM TITLE",
            "year": "3001",
            "artists": [_artist("ARTIST NAME", id="ARTIST ID", join=",")],
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
            "labels": [
                {
                    "name": "LABEL NAME",
                    "catno": "CATALOG NUMBER",
                }
            ],
            "tracklist": [],
        }

        if tracks:
            for recording in tracks:
                data["tracklist"].append(recording)

        return Bag(
            data=data,
            # Make some fields available as properties, as they are
            # accessed by DiscogsPlugin methods.
            title=data["title"],
            artists=[Bag(data=d) for d in data["artists"]],
        )

    def _make_track(self, title, position="", duration="", type_=None):
        track = {"title": title, "position": position, "duration": duration}
        if type_ is not None:
            # Test samples on discogs_client do not have a 'type_' field, but
            # the API seems to return it. Values: 'track' for regular tracks,
            # 'heading' for descriptive texts (ie. not real tracks - 12.13.2).
            track["type_"] = type_

        return track

    def _make_release_from_positions(self, positions):
        """Return a Bag that mimics a discogs_client.Release with a
        tracklist where tracks have the specified `positions`."""
        tracks = [
            self._make_track(f"TITLE{i}", position)
            for (i, position) in enumerate(positions, start=1)
        ]
        return self._make_release(tracks)

    def test_parse_media_for_tracks(self):
        tracks = [
            self._make_track("TITLE ONE", "1", "01:01"),
            self._make_track("TITLE TWO", "2", "02:02"),
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

    def test_parse_tracklist_without_sides(self):
        """Test standard Discogs position 12.2.9#1: "without sides"."""
        release = self._make_release_from_positions(["1", "2", "3"])
        d = DiscogsPlugin().get_album_info(release)

        assert d.mediums == 1
        assert len(d.tracks) == 3

    def test_parse_tracklist_with_sides(self):
        """Test standard Discogs position 12.2.9#2: "with sides"."""
        release = self._make_release_from_positions(["A1", "A2", "B1", "B2"])
        d = DiscogsPlugin().get_album_info(release)

        assert d.mediums == 1  # 2 sides = 1 LP
        assert len(d.tracks) == 4

    def test_parse_tracklist_multiple_lp(self):
        """Test standard Discogs position 12.2.9#3: "multiple LP"."""
        release = self._make_release_from_positions(["A1", "A2", "B1", "C1"])
        d = DiscogsPlugin().get_album_info(release)

        assert d.mediums == 2  # 3 sides = 1 LP + 1 LP
        assert len(d.tracks) == 4

    def test_parse_tracklist_multiple_cd(self):
        """Test standard Discogs position 12.2.9#4: "multiple CDs"."""
        release = self._make_release_from_positions(
            ["1-1", "1-2", "2-1", "3-1"]
        )
        d = DiscogsPlugin().get_album_info(release)

        assert d.mediums == 3
        assert len(d.tracks) == 4

    def test_parse_tracklist_non_standard(self):
        """Test non standard Discogs position."""
        release = self._make_release_from_positions(["I", "II", "III", "IV"])
        d = DiscogsPlugin().get_album_info(release)

        assert d.mediums == 1
        assert len(d.tracks) == 4

    def test_parse_tracklist_subtracks_dot(self):
        """Test standard Discogs position 12.2.9#5: "sub tracks, dots"."""
        release = self._make_release_from_positions(["1", "2.1", "2.2", "3"])
        d = DiscogsPlugin().get_album_info(release)

        assert d.mediums == 1
        assert len(d.tracks) == 3

        release = self._make_release_from_positions(
            ["A1", "A2.1", "A2.2", "A3"]
        )
        d = DiscogsPlugin().get_album_info(release)

        assert d.mediums == 1
        assert len(d.tracks) == 3

    def test_parse_tracklist_subtracks_letter(self):
        """Test standard Discogs position 12.2.9#5: "sub tracks, letter"."""
        release = self._make_release_from_positions(["A1", "A2a", "A2b", "A3"])
        d = DiscogsPlugin().get_album_info(release)

        assert d.mediums == 1
        assert len(d.tracks) == 3

        release = self._make_release_from_positions(
            ["A1", "A2.a", "A2.b", "A3"]
        )
        d = DiscogsPlugin().get_album_info(release)

        assert d.mediums == 1
        assert len(d.tracks) == 3

    def test_parse_tracklist_subtracks_extra_material(self):
        """Test standard Discogs position 12.2.9#6: "extra material"."""
        release = self._make_release_from_positions(["1", "2", "Video 1"])
        d = DiscogsPlugin().get_album_info(release)

        assert d.mediums == 2
        assert len(d.tracks) == 3

    def test_parse_tracklist_subtracks_indices(self):
        """Test parsing of subtracks that include index tracks."""
        release = self._make_release_from_positions(["", "", "1.1", "1.2"])
        # Track 1: Index track with medium title
        release.data["tracklist"][0]["title"] = "MEDIUM TITLE"
        # Track 2: Index track with track group title
        release.data["tracklist"][1]["title"] = "TRACK GROUP TITLE"

        d = DiscogsPlugin().get_album_info(release)
        assert d.mediums == 1
        assert d.tracks[0].disctitle == "MEDIUM TITLE"
        assert len(d.tracks) == 1
        assert d.tracks[0].title == "TRACK GROUP TITLE"

    def test_parse_tracklist_subtracks_nested_logical(self):
        """Test parsing of subtracks defined inside a index track that are
        logical subtracks (ie. should be grouped together into a single track).
        """
        release = self._make_release_from_positions(["1", "", "3"])
        # Track 2: Index track with track group title, and sub_tracks
        release.data["tracklist"][1]["title"] = "TRACK GROUP TITLE"
        release.data["tracklist"][1]["sub_tracks"] = [
            self._make_track("TITLE ONE", "2.1", "01:01"),
            self._make_track("TITLE TWO", "2.2", "02:02"),
        ]

        d = DiscogsPlugin().get_album_info(release)
        assert d.mediums == 1
        assert len(d.tracks) == 3
        assert d.tracks[1].title == "TRACK GROUP TITLE"

    def test_parse_tracklist_subtracks_nested_physical(self):
        """Test parsing of subtracks defined inside a index track that are
        physical subtracks (ie. should not be grouped together).
        """
        release = self._make_release_from_positions(["1", "", "4"])
        # Track 2: Index track with track group title, and sub_tracks
        release.data["tracklist"][1]["title"] = "TRACK GROUP TITLE"
        release.data["tracklist"][1]["sub_tracks"] = [
            self._make_track("TITLE ONE", "2", "01:01"),
            self._make_track("TITLE TWO", "3", "02:02"),
        ]

        d = DiscogsPlugin().get_album_info(release)
        assert d.mediums == 1
        assert len(d.tracks) == 4
        assert d.tracks[1].title == "TITLE ONE"
        assert d.tracks[2].title == "TITLE TWO"

    def test_parse_tracklist_disctitles(self):
        """Test parsing of index tracks that act as disc titles."""
        release = self._make_release_from_positions(
            ["", "1-1", "1-2", "", "2-1"]
        )
        # Track 1: Index track with medium title (Cd1)
        release.data["tracklist"][0]["title"] = "MEDIUM TITLE CD1"
        # Track 4: Index track with medium title (Cd2)
        release.data["tracklist"][3]["title"] = "MEDIUM TITLE CD2"

        d = DiscogsPlugin().get_album_info(release)
        assert d.mediums == 2
        assert d.tracks[0].disctitle == "MEDIUM TITLE CD1"
        assert d.tracks[1].disctitle == "MEDIUM TITLE CD1"
        assert d.tracks[2].disctitle == "MEDIUM TITLE CD2"
        assert len(d.tracks) == 3

    def test_parse_minimal_release(self):
        """Test parsing of a release with the minimal amount of information."""
        data = {
            "id": 123,
            "uri": "https://www.discogs.com/release/123456-something",
            "tracklist": [self._make_track("A", "1", "01:01")],
            "artists": [_artist("ARTIST NAME", id=321)],
            "title": "TITLE",
        }
        release = Bag(
            data=data,
            title=data["title"],
            artists=[Bag(data=d) for d in data["artists"]],
        )
        d = DiscogsPlugin().get_album_info(release)
        assert d.artist == "ARTIST NAME"
        assert d.album == "TITLE"
        assert len(d.tracks) == 1

    def test_parse_release_without_required_fields(self):
        """Test parsing of a release that does not have the required fields."""
        release = Bag(data={}, refresh=lambda *args: None)
        with capture_log() as logs:
            d = DiscogsPlugin().get_album_info(release)

        assert d is None
        assert "Release does not contain the required fields" in logs[0]

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
                _artist("OTHER ARTIST (5)", id=321),
            ],
            "title": "title",
            "labels": [
                {
                    "name": "LABEL NAME (5)",
                    "catno": "catalog number",
                }
            ],
        }
        release = Bag(
            data=data,
            title=data["title"],
            artists=[Bag(data=d) for d in data["artists"]],
        )
        d = DiscogsPlugin().get_album_info(release)
        assert d.artist == "ARTIST NAME & OTHER ARTIST"
        assert d.artists == ["ARTIST NAME", "OTHER ARTIST"]
        assert d.artists_ids == ["321", "321"]
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
                _artist("OTHER ARTIST (5)", id=321),
            ],
            "title": "title",
            "labels": [
                {
                    "name": "LABEL NAME (5)",
                    "catno": "catalog number",
                }
            ],
        }
        release = Bag(
            data=data,
            title=data["title"],
            artists=[Bag(data=d) for d in data["artists"]],
        )
        d = DiscogsPlugin().get_album_info(release)
        assert d.artist == "ARTIST NAME (2) & OTHER ARTIST (5)"
        assert d.artists == ["ARTIST NAME (2)", "OTHER ARTIST (5)"]
        assert d.tracks[0].artist == "TEST ARTIST (5)"
        assert d.tracks[0].artists == ["TEST ARTIST (5)"]
        assert d.label == "LABEL NAME (5)"
        config["discogs"]["strip_disambiguation"] = True


@patch("beetsplug.discogs.DiscogsPlugin.setup", Mock())
class DGSearchQueryTest(BeetsTestCase):
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
                    "artists": [_artist("ARTIST", id=11146, anv="ART")],
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
        release = Bag(
            data=data,
            title=data["title"],
            artists=[Bag(data=d) for d in data["artists"]],
        )
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


@patch("beetsplug.discogs.DiscogsPlugin.setup", Mock())
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
    release = Bag(
        data=data,
        title=data["title"],
        artists=[Bag(data=d) for d in data["artists"]],
    )
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


@pytest.mark.parametrize(
    (
        "track,expected_artist,expected_artists,expected_artists_ids,"
        "expected_composers"
    ),
    [
        (
            {
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
                    _artist(
                        "PERFORMER (1)", id=5, role="Other Role, Featuring"
                    ),
                    _artist("RANDOM", id=8, role="Written-By"),
                    _artist("MUSICIAN", id=10, role="Featuring [Uncredited]"),
                ],
            },
            "NEW ARTIST & VOCALIST feat. SOLOIST, PERFORMER, MUSICIAN",
            ["NEW ARTIST", "VOCALIST", "SOLOIST", "PERFORMER", "MUSICIAN"],
            ["11146", "344", "3", "5", "10"],
            ["RANDOM"],
        ),
    ],
)
@patch("beetsplug.discogs.DiscogsPlugin.setup", Mock())
def test_parse_featured_artists(
    track,
    expected_artist,
    expected_artists,
    expected_artists_ids,
    expected_composers,
):
    """Tests the plugins ability to parse a featured artist.
    Ignores artists that are not listed as featured."""
    plugin = DiscogsPlugin()
    artistinfo = ArtistState.from_config(plugin.config, [_artist("ARTIST")])
    t, _, _ = plugin.get_track_info(track, 1, 1, artistinfo)
    assert t.artist == expected_artist
    assert t.artists == expected_artists
    assert t.artists_ids == expected_artists_ids
    assert t.composers == expected_composers


@patch("beetsplug.discogs.DiscogsPlugin.setup", Mock())
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


@pytest.mark.parametrize(
    "given_artists,expected_info,config_va_name",
    [
        (
            [_artist("Various")],
            {
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
            },
            "VARIOUS ARTISTS",
        )
    ],
)
@patch("beetsplug.discogs.DiscogsPlugin.setup", Mock())
def test_va_buildartistinfo(given_artists, expected_info, config_va_name):
    config["va_name"] = config_va_name
    assert (
        ArtistState.from_config(DiscogsPlugin().config, given_artists).info
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
