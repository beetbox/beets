"""Tests for the 'tidal' plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

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


# --------------------------------- Mock Data -------------------------------- #
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
        track = _make_track("t1", "API Track", "PT3M", "ISRC001", ["a1"])
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
        assert info.track_id == "t1"
        assert info.artist == "API Artist"

    def test_track_for_id_not_found(self):
        """Test track_for_id returns None when not found."""
        self.tidal.api.get_tracks = Mock(return_value={"data": []})
        info = self.tidal.track_for_id("https://tidal.com/track/490839595")
        assert info is None

        info = self.tidal.track_for_id("does_not_exist")
        assert info is None


class TestAlbumForID(TidalPluginTest):
    """Tests for album_for_id with mocked API."""

    def test_album_for_id(self):
        """Test fetching album by ID via API."""
        track = _make_track("t1", "Album Track", "PT3M30S", "ISRC001", ["a1"])
        album, track_lookup, artist_lookup = _make_album(
            "al1", "API Album", [track], ["a1"]
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
        assert info.album_id == "al1"
        assert len(info.tracks) == 1
        assert info.tracks[0].title == "Album Track"

    def test_album_for_id_not_found(self):
        """Test album_for_id returns None when not found."""
        self.tidal.api.get_albums = Mock(return_value={"data": []})
        info = self.tidal.album_for_id("https://tidal.com/album/226495055")
        assert info is None

        info = self.tidal.album_for_id("does_not_exist")
        assert info is None


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
    def test_extract_data_url(self, attrs, expected):
        assert TidalPlugin._extract_data_url(attrs) == expected

    @pytest.mark.parametrize(
        "attrs, expected",
        [
            ({"copyright": {"text": "(P) 2024 Tidal"}}, "(P) 2024 Tidal"),
            ({}, None),
        ],
    )
    def test_extract_label(self, attrs, expected):
        assert TidalPlugin._extract_label(attrs) == expected

    @pytest.mark.parametrize(
        "attrs, expected",
        [
            ({"releaseDate": "2024-01-15"}, (2024, 1, 15)),
            ({}, None),
            ({"releaseDate": "2024"}, None),
        ],
    )
    def test_extract_release_date(self, attrs, expected):
        assert TidalPlugin._extract_release_date(attrs) == expected

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

    def test_duration_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid ISO 8601 duration"):
            TidalPlugin._duration_to_seconds("invalid")
