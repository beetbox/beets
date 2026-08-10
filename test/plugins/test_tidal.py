"""Tests for the 'tidal' plugin."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from beets.library.models import Item
from beets.test.helper import PluginTestHelper
from beetsplug.tidal import TidalPlugin

if TYPE_CHECKING:
    from beetsplug.tidal.api_types import (
        AlbumAttributes,
        RelationshipData,
        ResourceIdentifier,
        TidalAlbum,
        TidalArtist,
        TidalArtwork,
        TidalTrack,
        TrackAttributes,
    )

CURRENT_TS = 150000000


def _make_artwork(id_: str, href: str = "") -> TidalArtwork:
    return {
        "id": id_,
        "type": "artworks",
        "attributes": {
            "mediaType": "IMAGE",
            "files": [{"href": href, "meta": {"width": 1280, "height": 1280}}]
            if href
            else [],
        },
    }


def _make_artist(id_: str, name: str) -> TidalArtist:
    return {
        "id": id_,
        "type": "artists",
        "attributes": {"name": name, "popularity": 0.5},
    }


def _make_album(
    id_: str,
    title: str,
    tracks: list[TidalTrack],
    artist_ids: list[str],
    release_date: str = "2024-01-15",
    version: str | None = None,
    cover_art_id: str | None = None,
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

    relationships: dict[str, RelationshipData] = {
        "artists": {
            "data": [{"id": aid, "type": "artists"} for aid in artist_ids],
            "links": {},
        },
        "items": {
            "data": [{"id": t["id"], "type": "tracks"} for t in tracks],
            "links": {},
        },
    }
    if cover_art_id:
        relationships["coverArt"] = {
            "data": [{"id": cover_art_id, "type": "artworks"}],
            "links": {},
        }

    album: TidalAlbum = {
        "id": id_,
        "type": "albums",
        "attributes": attrs,
        "relationships": relationships,
    }
    return album, track_lookup, artist_lookup


def _make_track(
    id_: str,
    title: str,
    duration: str = "PT3M30S",
    isrc: str = "ISRC123",
    artist_ids: list[str] | None = None,
    version: str | None = None,
) -> TidalTrack:
    artist_relationships: list[ResourceIdentifier] = [
        {"id": aid, "type": "artists"} for aid in (artist_ids or [])
    ]
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
        "id": id_,
        "type": "tracks",
        "attributes": attrs,
        "relationships": {
            "artists": {"data": artist_relationships, "links": {}}
        },
    }


@pytest.fixture(autouse=True)
def set_current_ts(monkeypatch):
    monkeypatch.setattr("beetsplug.tidal.time.time", lambda: CURRENT_TS)


class TidalPluginTest(PluginTestHelper):
    plugin = "tidal"

    def setup_beets(self):
        super().setup_beets()
        self.tidal = TidalPlugin()


class TestParsing(TidalPluginTest):
    """High-level tests for album parsing."""

    def test_parse_album(self):
        tracks = [
            _make_track("101", "Track One", "PT3M", "ISRC1", ["1001"]),
            _make_track(
                "102",
                "Track Two",
                "PT4M",
                "ISRC2",
                ["1001"],
                version="Remastered",
            ),
        ]
        album, track_lookup, artist_lookup = _make_album(
            "1", "My Album", tracks, ["1001"], version="Deluxe Edition"
        )

        info = self.tidal._get_album_info(
            album, track_lookup, artist_lookup, {}
        )

        assert info.raw_data == {
            "album": "My Album (Deluxe Edition)",
            "album_id": "1",
            "albumdisambig": None,
            "albumstatus": None,
            "albumtype": "album",
            "albumtypes": ["album"],
            "artist": "Artist 1001",
            "artist_credit": None,
            "artist_id": "1001",
            "artist_sort": None,
            "artists": ["Artist 1001"],
            "artists_credit": None,
            "artists_ids": ["1001"],
            "artists_sort": None,
            "asin": None,
            "barcode": "123456",
            "catalognum": None,
            "country": None,
            "cover_art_url": None,
            "data_source": "Tidal",
            "data_url": None,
            "day": 15,
            "discogs_albumid": None,
            "discogs_artistid": None,
            "discogs_labelid": None,
            "duration": 2700,
            "genres": None,
            "label": None,
            "language": None,
            "media": None,
            "mediums": None,
            "month": 1,
            "original_day": None,
            "original_month": None,
            "original_year": None,
            "release_group_title": None,
            "releasegroup_id": None,
            "releasegroupdisambig": None,
            "script": None,
            "style": None,
            "tidal_album_id": "1",
            "tidal_album_popularity": 50,
            "tidal_artist_id": "1001",
            "tidal_updated": CURRENT_TS,
            "tracks": [
                {
                    "album": None,
                    "arrangers": None,
                    "arrangers_ids": [],
                    "artist": "Artist 1001",
                    "artist_credit": None,
                    "artist_id": None,
                    "artist_sort": None,
                    "artists": ["Artist 1001"],
                    "artists_credit": None,
                    "artists_ids": ["1001"],
                    "artists_sort": None,
                    "bpm": None,
                    "composer_sort": None,
                    "composers": None,
                    "composers_ids": [],
                    "data_source": "Tidal",
                    "data_url": None,
                    "disctitle": None,
                    "duration": 180,
                    "genres": None,
                    "index": 1,
                    "initial_key": None,
                    "isrc": "ISRC1",
                    "label": None,
                    "length": None,
                    "lyricists": None,
                    "lyricists_ids": [],
                    "mb_workid": None,
                    "media": None,
                    "medium": None,
                    "medium_index": None,
                    "medium_total": None,
                    "release_track_id": None,
                    "remixers": None,
                    "remixers_ids": [],
                    "tidal_artist_id": "1001",
                    "tidal_track_id": "101",
                    "tidal_track_popularity": 50,
                    "tidal_updated": CURRENT_TS,
                    "title": "Track One",
                    "track_alt": None,
                    "track_id": "101",
                    "work": None,
                    "work_disambig": None,
                },
                {
                    "album": None,
                    "arrangers": None,
                    "arrangers_ids": [],
                    "artist": "Artist 1001",
                    "artist_credit": None,
                    "artist_id": None,
                    "artist_sort": None,
                    "artists": ["Artist 1001"],
                    "artists_credit": None,
                    "artists_ids": ["1001"],
                    "artists_sort": None,
                    "bpm": None,
                    "composer_sort": None,
                    "composers": None,
                    "composers_ids": [],
                    "data_source": "Tidal",
                    "data_url": None,
                    "disctitle": None,
                    "duration": 240,
                    "genres": None,
                    "index": 2,
                    "initial_key": None,
                    "isrc": "ISRC2",
                    "label": None,
                    "length": None,
                    "lyricists": None,
                    "lyricists_ids": [],
                    "mb_workid": None,
                    "media": None,
                    "medium": None,
                    "medium_index": None,
                    "medium_total": None,
                    "release_track_id": None,
                    "remixers": None,
                    "remixers_ids": [],
                    "tidal_artist_id": "1001",
                    "tidal_track_id": "102",
                    "tidal_track_popularity": 50,
                    "tidal_updated": CURRENT_TS,
                    "title": "Track Two (Remastered)",
                    "track_alt": None,
                    "track_id": "102",
                    "work": None,
                    "work_disambig": None,
                },
            ],
            "va": False,
            "year": 2024,
        }

    def test_parse_album_with_version(self):
        """Album title should have version appended."""
        track = _make_track("101", "My Song", "PT3M", "ISRC001", ["1001"])
        album, track_lookup, artist_lookup = _make_album(
            "3", "My Album", [track], ["1001"], version="Deluxe Edition"
        )

        info = self.tidal._get_album_info(
            album, track_lookup, artist_lookup, {}
        )

        assert info.album == "My Album (Deluxe Edition)"


class TestArtworkParsing(TidalPluginTest):
    """Tests for artwork URL parsing."""

    def test_artwork_with_url(self):
        """Cover art URL from included resources."""
        track = _make_track("t1", "Song", "PT3M", "ISRC001", ["a1"])
        album, track_lookup, artist_lookup = _make_album(
            "al1", "Album", [track], ["a1"], cover_art_id="ca1"
        )
        artwork_lookup = {
            "ca1": _make_artwork(
                "ca1", "https://resources.tidal.com/images/ca1/1280x1280.jpg"
            )
        }

        info = self.tidal._get_album_info(
            album, track_lookup, artist_lookup, artwork_lookup
        )

        assert (
            info.cover_art_url
            == "https://resources.tidal.com/images/ca1/1280x1280.jpg"
        )

    def test_artwork_without_files_returns_none(self):
        """Cover art returns None when files array is empty."""
        track = _make_track("t1", "Song", "PT3M", "ISRC001", ["a1"])
        album, track_lookup, artist_lookup = _make_album(
            "al1", "Album", [track], ["a1"], cover_art_id="ca1"
        )
        artwork_lookup = {"ca1": _make_artwork("ca1")}

        info = self.tidal._get_album_info(
            album, track_lookup, artist_lookup, artwork_lookup
        )

        assert info.cover_art_url is None

    def test_artwork_without_relationship_returns_none(self):
        """No cover_art_url when album has no coverArt relationship."""
        track = _make_track("t1", "Song", "PT3M", "ISRC001", ["a1"])
        album, track_lookup, artist_lookup = _make_album(
            "al1", "Album", [track], ["a1"]
        )

        info = self.tidal._get_album_info(
            album, track_lookup, artist_lookup, {}
        )

        assert info.cover_art_url is None


class TestTrackParsing(TidalPluginTest):
    """High-level tests for track parsing."""

    def test_parse_track(self):
        track = _make_track("101", "My Track", "PT4M", "ISRC456", ["1001"])
        artist_lookup = {"1001": _make_artist("1001", "My Artist")}

        info = self.tidal._get_track_info(track, artist_lookup)

        assert info.title == "My Track"
        assert info.track_id == "101"
        assert info.duration == 240  # PT4M = 240 seconds
        assert info.isrc == "ISRC456"
        assert info.artist == "My Artist"
        assert info.tidal_track_id == "101"
        assert info.tidal_artist_id == "1001"
        assert info.tidal_track_popularity == 50

    def test_parse_track_with_version(self):
        """Track title should have version appended."""
        track = _make_track(
            "102", "My Song", "PT3M", "ISRC002", ["1001"], version="Remastered"
        )
        artist_lookup = {"1001": _make_artist("1001", "My Artist")}

        info = self.tidal._get_track_info(track, artist_lookup)

        assert info.title == "My Song (Remastered)"
        assert info.tidal_track_id == "102"


class TestTrackForID(TidalPluginTest):
    """Tests for track_for_id with mocked API."""

    def test_track_for_id(self):
        """Test fetching track by ID via API."""
        track = _make_track(
            "490839595", "API Track", "PT3M", "ISRC001", ["1001"]
        )
        artist = _make_artist("1001", "API Artist")

        self.tidal.api.get_tracks = Mock(
            return_value={"data": [track], "included": [artist]}
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
            "490839595", "API Track 1", "PT3M", "ISRC001", ["1001"]
        )
        track2 = _make_track(
            "490839596", "API Track 2", "PT4M", "ISRC002", ["1001"]
        )
        artist = _make_artist("1001", "API Artist")

        self.tidal.api.get_tracks = Mock(
            return_value={"data": [track1, track2], "included": [artist]}
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
        track = _make_track(
            "490839595", "API Track", "PT3M", "ISRC001", ["1001"]
        )
        artist = _make_artist("1001", "API Artist")

        self.tidal.api.get_tracks = Mock(
            return_value={"data": [track], "included": [artist]}
        )

        results = list(
            self.tidal.tracks_for_ids(
                ["https://tidal.com/track/490839595", "does_not_exist"]
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
        track = _make_track(
            "101", "Album Track", "PT3M30S", "ISRC001", ["1001"]
        )
        album, track_lookup, artist_lookup = _make_album(
            "226495055", "API Album", [track], ["1001"]
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
        track1 = _make_track(
            "101", "Album Track 1", "PT3M", "ISRC001", ["1001"]
        )
        track2 = _make_track(
            "102", "Album Track 2", "PT4M", "ISRC002", ["1001"]
        )
        album1, track_lookup1, artist_lookup1 = _make_album(
            "226495055", "API Album 1", [track1], ["1001"]
        )
        album2, track_lookup2, artist_lookup2 = _make_album(
            "226495056", "API Album 2", [track2], ["1001"]
        )

        # Combine lookups to simulate API response
        all_included = [
            *artist_lookup1.values(),
            *artist_lookup2.values(),
            *track_lookup1.values(),
            *track_lookup2.values(),
        ]

        self.tidal.api.get_albums = Mock(
            return_value={"data": [album1, album2], "included": all_included}
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
        track = _make_track("101", "Album Track", "PT3M", "ISRC001", ["1001"])
        album, track_lookup, artist_lookup = _make_album(
            "226495055", "API Album", [track], ["1001"]
        )

        self.tidal.api.get_albums = Mock(
            return_value={
                "data": [album],
                "included": [*artist_lookup.values(), *track_lookup.values()],
            }
        )

        results = list(
            self.tidal.albums_for_ids(
                ["https://tidal.com/album/226495055", "does_not_exist"]
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
        track = _make_track("101", "Album Track", "PT3M", "ISRC001", ["1001"])
        album, track_lookup, artist_lookup = _make_album(
            "1", "Barcode Album", [track], ["1001"]
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
                        "albums": {"data": [{"id": "1", "type": "albums"}]}
                    }
                }
            }
        )

        # Mock album lookup by ID
        track = _make_track("101", "Album Track", "PT3M", "ISRC001", ["1001"])
        album, track_lookup, artist_lookup = _make_album(
            "1", "Query Album", [track], ["1001"]
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
            "490839595", "ISRC Track", "PT3M", "ISRC001", ["1001"]
        )
        artist = _make_artist("1001", "ISRC Artist")

        self.tidal.api.get_tracks = Mock(
            return_value={"data": [track], "included": [artist]}
        )

        item = Item(isrc="ISRC001")

        results = list(self.tidal.item_candidates(item, "Artist", "Title"))

        self.tidal.api.get_tracks.assert_called_once()
        assert len(results) == 1
        assert results[0].title == "ISRC Track"

    def test_item_candidates_with_query_fallback(self):
        """Test item_candidates falls back to query search when no ISRC."""
        item = Item(title="Query Song", artist="Query Artist")

        self.tidal.api.search_results = Mock(
            return_value={
                "data": {
                    "relationships": {
                        "tracks": {
                            "data": [{"id": "490839595", "type": "tracks"}]
                        }
                    }
                },
                "included": [
                    _make_track(
                        "490839595", "Query Track", "PT3M", "ISRC002", ["1001"]
                    ),
                    _make_artist("1001", "Query Artist"),
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

    def test_popularity_with_float(self):
        assert TidalPlugin._parse_popularity({"popularity": 0.5}) == 50
        assert TidalPlugin._parse_popularity({"popularity": 1.0}) == 100
        assert TidalPlugin._parse_popularity({"popularity": 0.0}) == 0

    @pytest.mark.parametrize(
        "artwork_data, artwork_by_id, expected",
        [
            (
                [{"id": "ca1", "type": "artworks"}],
                {
                    "ca1": {
                        "id": "ca1",
                        "type": "artworks",
                        "attributes": {
                            "mediaType": "IMAGE",
                            "files": [
                                {
                                    "href": "https://example.com/cover.jpg",
                                    "meta": {"width": 1280, "height": 1280},
                                }
                            ],
                        },
                    }
                },
                "https://example.com/cover.jpg",
            ),
            (
                [{"id": "ca1", "type": "artworks"}],
                {
                    "ca1": {
                        "id": "ca1",
                        "type": "artworks",
                        "attributes": {"mediaType": "IMAGE", "files": []},
                    }
                },
                None,
            ),
            # No artworks in relationship data
            ([{"id": "ca1", "type": "coverArts"}], {}, None),
            # No cover art lookup
            ([{"id": "ca1", "type": "artworks"}], {}, None),
            # Empty relationships
            ({}, {}, None),
        ],
    )
    def test_parse_artwork_url(self, artwork_data, artwork_by_id, expected):
        album: TidalAlbum = {
            "id": "al1",
            "type": "albums",
            "attributes": {
                "albumType": "ALBUM",
                "barcodeId": "123",
                "duration": "PT45M",
                "explicit": False,
                "mediaTags": [],
                "numberOfItems": 1,
                "numberOfVolumes": 1,
                "popularity": 0.5,
                "title": "Album",
            },
            "relationships": {"coverArt": {"data": artwork_data, "links": {}}}
            if artwork_data
            else {},
        }
        assert TidalPlugin._parse_artwork_url(album, artwork_by_id) == expected


class TestTidalsync(TidalPluginTest):
    """Tests for the tidalsync command."""

    def _run_tidalsync(self, *args: str) -> None:
        command = next(
            cmd for cmd in self.tidal.commands() if cmd.name == "tidalsync"
        )
        opts, subargs = command.parser.parse_args(list(args))
        command.func(self.lib, opts, subargs)

    def test_sync_updates_popularity(self):
        """Test sync_item_popularity fetches and stores popularity."""
        item = self.add_item(
            tidal_track_id=490839595, title="Test Track", artist="Test Artist"
        )

        track = _make_track(
            "490839595", "Test Track", "PT3M", "ISRC001", ["1001"]
        )
        artist = _make_artist("1001", "Test Artist")

        self.tidal.api.get_tracks = Mock(
            return_value={"data": [track], "included": [artist]}
        )

        self.tidal.sync_item_popularity([item], write=False)

        assert item["tidal_track_popularity"] == 50
        assert item["tidal_updated"] is not None
        assert isinstance(item["tidal_updated"], (int, float))

    def test_sync_skips_existing(self):
        """Test sync_item_popularity skips items with existing popularity."""
        item = self.add_item(
            tidal_track_id=490839595,
            tidal_track_popularity=42,
            tidal_updated=time.time(),
            title="Test Track",
            artist="Test Artist",
        )

        self.tidal.sync_item_popularity([item], write=False)

        assert item["tidal_track_popularity"] == 42

    def test_sync_force_updates_existing(self):
        """Test sync_item_popularity with force re-fetches."""
        item = self.add_item(
            tidal_track_id=490839595,
            tidal_track_popularity=42,
            tidal_updated=time.time(),
            title="Test Track",
            artist="Test Artist",
        )

        track = _make_track(
            "490839595", "Test Track", "PT3M", "ISRC001", ["1001"]
        )
        artist = _make_artist("1001", "Test Artist")

        self.tidal.api.get_tracks = Mock(
            return_value={"data": [track], "included": [artist]}
        )

        self.tidal.sync_item_popularity([item], write=False, force=True)

        assert item["tidal_track_popularity"] == 50

    def test_sync_skips_items_without_track_id(self):
        """Test sync_item_popularity skips items without tidal_track_id."""
        item = self.add_item(title="No ID Track", artist="No ID Artist")

        self.tidal.sync_item_popularity([item], write=False)

        assert item.get("tidal_track_popularity") is None

    def test_sync_does_not_update_when_lookup_is_missing(self):
        """Test sync_item_popularity leaves stale data untouched on miss."""
        item = self.add_item(
            tidal_track_id="490839595",
            title="Missing Track",
            artist="Missing Artist",
        )

        self.tidal.api.get_tracks = Mock(
            return_value={"data": [], "included": []}
        )

        self.tidal.sync_item_popularity([item], write=False)

        assert item.get("tidal_track_popularity") is None
        assert item.get("tidal_updated") is None

    def test_sync_updates_album_popularity(self):
        """Test sync_album_popularity fetches and stores album popularity."""
        item = self.add_item(
            tidal_track_id="490839595",
            tidal_album_id="251380836",
            title="Test Track",
            artist="Test Artist",
        )

        track = _make_track(
            "490839595", "Test Track", "PT3M", "ISRC001", ["1001"]
        )
        artist = _make_artist("1001", "Test Artist")

        album_track = _make_track(
            "101", "Album Track", "PT3M", "ISRC001", ["1001"]
        )
        album_data, _, artist_lookup = _make_album(
            "251380836", "Test Album", [album_track], ["1001"]
        )

        album = self.lib.add_album([item])
        album["tidal_album_id"] = "251380836"
        album.store()

        self.tidal.api.get_tracks = Mock(
            return_value={"data": [track], "included": [artist]}
        )
        self.tidal.api.get_albums = Mock(
            return_value={
                "data": [album_data],
                "included": [*artist_lookup.values()],
            }
        )

        self.tidal.sync_item_popularity([item], write=False)
        self.tidal.sync_album_popularity([album], write=False)

        assert item["tidal_track_popularity"] == 50
        assert album["tidal_album_popularity"] == 50
        assert item["tidal_updated"] is not None

    def test_tidalsync_uses_first_query_argument(self):
        self.lib.items = Mock(return_value=["items"])
        self.tidal.sync_item_popularity = Mock()

        self._run_tidalsync("path::aaa")

        self.lib.items.assert_called_once_with(
            ["data_source:tidal", "path::aaa"]
        )
        self.tidal.sync_item_popularity.assert_called_once_with(
            ["items"], write=False, force=False
        )

    def test_tidalsync_defaults_to_items(self):
        self.lib.items = Mock(return_value=["items"])
        self.tidal.sync_item_popularity = Mock()
        self.tidal.sync_album_popularity = Mock()

        self._run_tidalsync()

        self.lib.items.assert_called_once_with(["data_source:tidal"])
        self.tidal.sync_item_popularity.assert_called_once_with(
            ["items"], write=False, force=False
        )
        self.tidal.sync_album_popularity.assert_not_called()

    def test_tidalsync_album_mode_uses_album_query(self):
        self.lib.albums = Mock(return_value=["albums"])
        self.tidal.sync_item_popularity = Mock()
        self.tidal.sync_album_popularity = Mock()

        self._run_tidalsync("-a", "artist:Test")

        self.lib.albums.assert_called_once_with(
            ["data_source:tidal", "artist:Test"]
        )
        self.tidal.sync_album_popularity.assert_called_once_with(
            ["albums"], write=False, force=False
        )
        self.tidal.sync_item_popularity.assert_not_called()
