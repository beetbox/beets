"""Tests for the 'tidal' plugin."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from beets.library.models import Item
from beets.test.helper import PluginTestCase
from beetsplug.tidal import TidalPlugin

if TYPE_CHECKING:
    from beetsplug.tidal.api_types import (
        AlbumAttributes,
        TidalAlbum,
        TidalArtist,
        TidalTrack,
        TrackAttributes,
    )


def _make_artist(id: str, name: str) -> TidalArtist:
    return {
        "id": id,
        "type": "artists",
        "attributes": {"name": name, "popularity": 0.5},
    }


def _make_album(
    id: str,
    title: str,
    tracks: list[TidalTrack],
    artist_ids: list[str],
    release_date: str = "2024-01-15",
    version: str | None = None,
) -> tuple[TidalAlbum, dict[str, TidalTrack], dict[str, TidalArtist]]:
    artist_lookup = {
        aid: _make_artist(aid, f"Artist {aid}") for aid in artist_ids
    }
    track_lookup = {t["id"]: t for t in tracks}

    attrs: AlbumAttributes = {
        "albumType": "ALBUM",
        "barcodeId": "123456",
        "duration": "PT45M",
        "explicit": False,
        "mediaTags": [],
        "numberOfItems": len(tracks),
        "numberOfVolumes": 1,
        "popularity": 0.5,
        "title": title,
        "releaseDate": release_date,
    }
    if version:
        attrs["version"] = version

    album: TidalAlbum = {
        "id": id,
        "type": "albums",
        "attributes": attrs,
        "relationships": {
            "artists": {
                "data": [{"id": aid, "type": "artists"} for aid in artist_ids],
                "links": {},
            },
            "items": {
                "data": [{"id": t["id"], "type": "tracks"} for t in tracks],
                "links": {},
            },
        },
    }
    return album, track_lookup, artist_lookup


def _make_track(
    id: str,
    title: str,
    duration: str = "PT3M30S",
    isrc: str = "ISRC123",
    artist_ids: list[str] | None = None,
    version: str | None = None,
) -> TidalTrack:
    attrs: TrackAttributes = {
        "title": title,
        "duration": duration,
        "explicit": False,
        "isrc": isrc,
        "key": "C",
        "keyScale": "MAJOR",
        "mediaTags": [],
        "popularity": 0.5,
    }
    if version:
        attrs["version"] = version
    return {
        "id": id,
        "type": "tracks",
        "attributes": attrs,
        "relationships": {
            "artists": {
                "data": [
                    {"id": aid, "type": "artists"} for aid in (artist_ids or [])
                ],
                "links": {},
            },
        },
    }


class TidalPluginTest(PluginTestCase):
    plugin = "tidal"

    def setUp(self):
        super().setUp()
        self.tidal = TidalPlugin()


class TestAlbumParsing(TidalPluginTest):
    """High-level tests for album parsing."""

    def test_parse_album(self):
        track = _make_track("t1", "My Song", "PT3M30S", "ISRC001", ["a1"])
        album, track_lookup, artist_lookup = _make_album(
            "al1", "My Album", [track], ["a1"]
        )

        info = self.tidal._get_album_info(album, track_lookup, artist_lookup)

        assert info.album == "My Album"
        assert info.album_id == "al1"
        assert len(info.tracks) == 1
        assert info.tracks[0].title == "My Song"

    def test_parse_album_with_multiple_tracks(self):
        tracks = [
            _make_track("t1", "Track One", "PT3M", "ISRC1", ["a1"]),
            _make_track("t2", "Track Two", "PT4M", "ISRC2", ["a1"]),
        ]
        album, track_lookup, artist_lookup = _make_album(
            "al2", "Album Two", tracks, ["a1"]
        )

        info = self.tidal._get_album_info(
            album,
            track_lookup,
            artist_lookup,
        )

        assert len(info.tracks) == 2
        assert info.tracks[0].index == 1
        assert info.tracks[1].index == 2

    def test_parse_album_with_version(self):
        """Album title should have version appended."""
        track = _make_track("t1", "My Song", "PT3M", "ISRC001", ["a1"])
        album, track_lookup, artist_lookup = _make_album(
            "al3", "My Album", [track], ["a1"], version="Deluxe Edition"
        )

        info = self.tidal._get_album_info(album, track_lookup, artist_lookup)

        assert info.album == "My Album (Deluxe Edition)"


class TestTrackParsing(TidalPluginTest):
    """High-level tests for track parsing."""

    def test_parse_track(self):
        track = _make_track("t1", "My Track", "PT4M", "ISRC456", ["a1"])
        artist_lookup = {"a1": _make_artist("a1", "My Artist")}

        info = self.tidal._get_track_info(track, artist_lookup)

        assert info.title == "My Track"
        assert info.track_id == "t1"
        assert info.duration == 240  # PT4M = 240 seconds
        assert info.isrc == "ISRC456"
        assert info.artist == "My Artist"

    def test_parse_track_with_version(self):
        """Track title should have version appended."""
        track = _make_track(
            "t2", "My Song", "PT3M", "ISRC002", ["a1"], version="Remastered"
        )
        artist_lookup = {"a1": _make_artist("a1", "My Artist")}

        info = self.tidal._get_track_info(track, artist_lookup)

        assert info.title == "My Song (Remastered)"


class TestTrackForID(TidalPluginTest):
    """Tests for track_for_id with mocked API."""

    def test_track_for_id(self):
        """Test fetching track by ID via API."""
        track = _make_track("490839595", "API Track", "PT3M", "ISRC001", ["a1"])
        artist = _make_artist("a1", "API Artist")

        self.tidal.api.get_tracks = Mock(
            return_value={
                "data": [track],
                "included": [artist],
            }
        )

        info = self.tidal.track_for_id("https://tidal.com/track/490839595")
        self.tidal.api.get_tracks.assert_called_once()

        assert info is not None
        assert info.title == "API Track"
        assert info.track_id == "490839595"
        assert info.artist == "API Artist"

    def test_track_for_id_not_found(self):
        """Test track_for_id returns None when not found."""
        self.tidal.api.get_tracks = Mock(return_value={"data": []})
        info = self.tidal.track_for_id("https://tidal.com/track/490839595")
        assert info is None

        info = self.tidal.track_for_id("does_not_exist")
        assert info is None


class TestTracksForIDs(TidalPluginTest):
    """Tests for tracks_for_ids with mocked API."""

    def test_tracks_for_ids(self):
        """Test fetching multiple tracks by IDs via API."""
        track1 = _make_track(
            "490839595", "API Track 1", "PT3M", "ISRC001", ["a1"]
        )
        track2 = _make_track(
            "490839596", "API Track 2", "PT4M", "ISRC002", ["a1"]
        )
        artist = _make_artist("a1", "API Artist")

        self.tidal.api.get_tracks = Mock(
            return_value={
                "data": [track1, track2],
                "included": [artist],
            }
        )

        results = list(
            self.tidal.tracks_for_ids(
                [
                    "https://tidal.com/track/490839595",
                    "https://tidal.com/track/490839596",
                ]
            )
        )
        self.tidal.api.get_tracks.assert_called_once()
        assert len(results) == 2
        assert results[0] is not None
        assert results[0].title == "API Track 1"
        assert results[1] is not None
        assert results[1].title == "API Track 2"

    def test_tracks_for_ids_with_missing(self):
        """Test tracks_for_ids yields None for IDs not found."""
        track = _make_track("490839595", "API Track", "PT3M", "ISRC001", ["a1"])
        artist = _make_artist("a1", "API Artist")

        self.tidal.api.get_tracks = Mock(
            return_value={
                "data": [track],
                "included": [artist],
            }
        )

        results = list(
            self.tidal.tracks_for_ids(
                [
                    "https://tidal.com/track/490839595",
                    "does_not_exist",
                ]
            )
        )

        assert len(results) == 2
        assert results[0] is not None
        assert results[0].title == "API Track"
        assert results[1] is None


class TestAlbumForID(TidalPluginTest):
    """Tests for album_for_id with mocked API."""

    def test_album_for_id(self):
        """Test fetching album by ID via API."""
        track = _make_track("t1", "Album Track", "PT3M30S", "ISRC001", ["a1"])
        album, track_lookup, artist_lookup = _make_album(
            "226495055", "API Album", [track], ["a1"]
        )
        self.tidal.api.get_albums = Mock(
            return_value={
                "data": [album],
                "included": [*artist_lookup.values(), *track_lookup.values()],
            }
        )

        info = self.tidal.album_for_id("https://tidal.com/album/226495055")

        assert info is not None
        assert info.album == "API Album"
        assert info.album_id == "226495055"
        assert len(info.tracks) == 1
        assert info.tracks[0].title == "Album Track"

    def test_album_for_id_not_found(self):
        """Test album_for_id returns None when not found."""
        self.tidal.api.get_albums = Mock(return_value={"data": []})
        info = self.tidal.album_for_id("https://tidal.com/album/226495055")
        assert info is None

        info = self.tidal.album_for_id("does_not_exist")
        assert info is None


class TestAlbumsForIDs(TidalPluginTest):
    """Tests for albums_for_ids with mocked API."""

    def test_albums_for_ids(self):
        """Test fetching multiple albums by IDs via API."""
        track1 = _make_track("t1", "Album Track 1", "PT3M", "ISRC001", ["a1"])
        track2 = _make_track("t2", "Album Track 2", "PT4M", "ISRC002", ["a1"])
        album1, track_lookup1, artist_lookup1 = _make_album(
            "226495055", "API Album 1", [track1], ["a1"]
        )
        album2, track_lookup2, artist_lookup2 = _make_album(
            "226495056", "API Album 2", [track2], ["a1"]
        )

        # Combine lookups to simulate API response
        all_included = [
            *artist_lookup1.values(),
            *artist_lookup2.values(),
            *track_lookup1.values(),
            *track_lookup2.values(),
        ]

        self.tidal.api.get_albums = Mock(
            return_value={
                "data": [album1, album2],
                "included": all_included,
            }
        )

        results = list(
            self.tidal.albums_for_ids(
                [
                    "https://tidal.com/album/226495055",
                    "https://tidal.com/album/226495056",
                ]
            )
        )

        self.tidal.api.get_albums.assert_called_once()
        # Note: yields album then None for each ID
        assert len(results) == 2
        assert results[0] is not None
        assert results[0].album == "API Album 1"
        assert results[1] is not None
        assert results[1].album == "API Album 2"

    def test_albums_for_ids_with_missing(self):
        """Test albums_for_ids yields None for IDs not found."""
        track = _make_track("t1", "Album Track", "PT3M", "ISRC001", ["a1"])
        album, track_lookup, artist_lookup = _make_album(
            "226495055", "API Album", [track], ["a1"]
        )

        self.tidal.api.get_albums = Mock(
            return_value={
                "data": [album],
                "included": [*artist_lookup.values(), *track_lookup.values()],
            }
        )

        results = list(
            self.tidal.albums_for_ids(
                [
                    "https://tidal.com/album/226495055",
                    "does_not_exist",
                ]
            )
        )

        # yields (album, None) for (found, not_found)
        assert len(results) == 2
        assert results[0] is not None
        assert results[0].album == "API Album"
        assert results[1] is None


class TestCandidates(TidalPluginTest):
    """Tests for candidates method."""

    def test_candidates_with_barcode(self):
        """Test that candidates uses barcode lookup first."""
        track = _make_track("t1", "Album Track", "PT3M", "ISRC001", ["a1"])
        album, track_lookup, artist_lookup = _make_album(
            "al1", "Barcode Album", [track], ["a1"]
        )

        self.tidal.api.get_albums = Mock(
            return_value={
                "data": [album],
                "included": [*artist_lookup.values(), *track_lookup.values()],
            }
        )

        items = [Item(barcode="123456")]

        candidates = list(
            self.tidal.candidates(items, "Artist", "Album", False)
        )

        self.tidal.api.get_albums.assert_called_once()
        assert len(candidates) == 1
        assert candidates[0].album == "Barcode Album"

    def test_candidates_with_query_fallback(self):
        """Test that candidates falls back to query search when no barcode."""
        items = [Item(title="My Song", artist="My Artist", album="My Album")]

        # Mock search returning album IDs
        self.tidal.api.search_results = Mock(
            return_value={
                "data": {
                    "relationships": {
                        "albums": {
                            "data": [{"id": "al1", "type": "albums"}],
                        },
                    },
                },
            }
        )

        # Mock album lookup by ID
        track = _make_track("t1", "Album Track", "PT3M", "ISRC001", ["a1"])
        album, track_lookup, artist_lookup = _make_album(
            "al1", "Query Album", [track], ["a1"]
        )
        self.tidal.api.get_albums = Mock(
            return_value={
                "data": [album],
                "included": [*artist_lookup.values(), *track_lookup.values()],
            }
        )

        candidates = list(
            self.tidal.candidates(items, "My Artist", "My Album", False)
        )

        # Should have called search_results
        assert self.tidal.api.search_results.called
        assert len(candidates) == 1
        assert candidates[0].album == "Query Album"


class TestItemCandidates(TidalPluginTest):
    """Tests for item_candidates method."""

    def test_item_candidates_with_isrc(self):
        """Test that item_candidates uses ISRC lookup first."""
        track = _make_track(
            "490839595", "ISRC Track", "PT3M", "ISRC001", ["a1"]
        )
        artist = _make_artist("a1", "ISRC Artist")

        self.tidal.api.get_tracks = Mock(
            return_value={
                "data": [track],
                "included": [artist],
            }
        )

        item = Item(isrc="ISRC001")

        results = list(self.tidal.item_candidates(item, "Artist", "Title"))

        self.tidal.api.get_tracks.assert_called_once()
        assert len(results) == 1
        assert results[0].title == "ISRC Track"

    def test_item_candidates_with_query_fallback(self):
        """Test that item_candidates falls back to query search when no ISRC."""
        item = Item(title="Query Song", artist="Query Artist")

        self.tidal.api.search_results = Mock(
            return_value={
                "data": {
                    "relationships": {
                        "tracks": {
                            "data": [{"id": "490839595", "type": "tracks"}],
                        },
                    },
                },
                "included": [
                    _make_track(
                        "490839595", "Query Track", "PT3M", "ISRC002", ["a1"]
                    ),
                    _make_artist("a1", "Query Artist"),
                ],
            }
        )

        results = list(
            self.tidal.item_candidates(item, "Query Artist", "Query Song")
        )

        assert self.tidal.api.search_results.called
        assert results[0].title == "Query Track"


class TestStaticHelpers:
    """Tests for static helper methods."""

    @pytest.mark.parametrize(
        "attrs, expected",
        [
            (
                {
                    "externalLinks": [
                        {"href": "https://tidal.com/b/123", "meta": ""}
                    ]
                },
                "https://tidal.com/b/123",
            ),
            ({}, None),
        ],
    )
    def test_parse_data_url(self, attrs, expected):
        assert TidalPlugin._parse_data_url(attrs) == expected

    @pytest.mark.parametrize(
        "attrs, expected",
        [
            ({"copyright": {"text": "(P) 2024 Tidal"}}, "(P) 2024 Tidal"),
            ({}, None),
        ],
    )
    def test_parse_label(self, attrs, expected):
        assert TidalPlugin._parse_label(attrs) == expected

    @pytest.mark.parametrize(
        "attrs, expected",
        [
            ({"releaseDate": "2024-01-15"}, (2024, 1, 15)),
            ({}, None),
            ({"releaseDate": "2024"}, None),
        ],
    )
    def test_parse_release_date(self, attrs, expected):
        assert TidalPlugin._parse_release_date(attrs) == expected

    @pytest.mark.parametrize(
        "duration,expected",
        [
            ("PT30S", 30),
            ("PT3M30S", 210),
            ("PT4M", 240),
            ("PT1H", 3600),
            ("PT1H30M", 5400),
        ],
    )
    def test_duration_conversions(self, duration, expected):
        assert TidalPlugin._duration_to_seconds(duration) == expected

    def test_duration_invalid_raises(self, caplog):
        with caplog.at_level(logging.WARNING):
            TidalPlugin._duration_to_seconds("invalid")
        assert "Invalid ISO 8601 duration: invalid" in caplog.text
