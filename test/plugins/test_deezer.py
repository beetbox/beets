"""Tests for the 'deezer' plugin."""

from __future__ import annotations

from typing import Any

from beets import config
from beetsplug.deezer import VARIOUS_ARTISTS_ID, DeezerPlugin


def _album_data(
    artist_id: int = 321, artist_name: str = "Album Artist"
) -> dict[str, Any]:
    return {
        "id": 123,
        "title": "Album Title",
        "artist": {"id": artist_id, "name": artist_name},
        "release_date": "2024-04-05",
        "record_type": "album",
        "label": "Example Label",
        "link": "https://www.deezer.com/album/123",
        "cover_xl": "https://e-cdns-images.dzcdn.net/images/cover/example",
    }


def _track_data() -> dict[str, Any]:
    return {
        "id": 456,
        "title": "Track Title",
        "artist": {"id": 654, "name": "Track Artist"},
        "duration": 180,
        "track_position": 1,
        "disk_number": 1,
        "rank": 100,
        "link": "https://www.deezer.com/track/456",
    }


def _plugin_with_album(monkeypatch, album_data: dict[str, Any]) -> DeezerPlugin:
    plugin = DeezerPlugin()

    def fetch_data(url: str):
        if url == f"{plugin.album_url}123":
            return album_data
        if url == f"{plugin.album_url}123/tracks":
            return {"data": [_track_data()]}
        raise AssertionError(f"Unexpected Deezer URL: {url}")

    monkeypatch.setattr(plugin, "fetch_data", fetch_data)
    return plugin


def test_album_for_id_uses_album_artist_when_contributors_missing(monkeypatch):
    plugin = _plugin_with_album(monkeypatch, _album_data())

    info = plugin.album_for_id("123")

    assert info is not None
    assert info.artist == "Album Artist"
    assert info.artist_credit == "Album Artist"
    assert info.artist_id == "321"


def test_album_for_id_keeps_contributors_when_present(monkeypatch):
    album_data = _album_data()
    album_data["contributors"] = [
        {"id": 654, "name": "Track Artist", "role": "Main"}
    ]
    plugin = _plugin_with_album(monkeypatch, album_data)

    info = plugin.album_for_id("123")

    assert info is not None
    assert info.artist == "Track Artist"
    assert info.artist_credit == "Album Artist"
    assert info.artist_id == "654"


def test_album_for_id_keeps_va_name_when_contributors_missing(monkeypatch):
    plugin = _plugin_with_album(
        monkeypatch, _album_data(VARIOUS_ARTISTS_ID, "Various Artists")
    )

    info = plugin.album_for_id("123")

    assert info is not None
    assert info.artist == config["va_name"].as_str()
    assert info.artist_credit == config["va_name"].as_str()
    assert info.artist_id == str(VARIOUS_ARTISTS_ID)
