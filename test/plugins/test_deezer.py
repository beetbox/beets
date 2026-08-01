"""Tests for the 'deezer' plugin"""

import responses

from beets.test.helper import PluginTestCase
from beetsplug import deezer


def _album_payload(album_artist_id, track_artist_ids):
    """Build minimal Deezer album and tracks payloads.

    ``album_artist_id`` is the release's "main" artist; ``track_artist_ids``
    lists the primary artist of each track.
    """
    contributor_ids = dict.fromkeys([album_artist_id, *track_artist_ids])
    album = {
        "title": "Some Album",
        "link": "https://www.deezer.com/album/1",
        "record_type": "album",
        "label": "Some Label",
        "release_date": "2017-01-01",
        "artist": {"id": album_artist_id, "name": f"Artist {album_artist_id}"},
        "contributors": [
            {"id": aid, "name": f"Artist {aid}"} for aid in contributor_ids
        ],
        "cover_xl": None,
    }
    tracks = {
        "data": [
            {
                "title": f"Track {i}",
                "id": 1000 + i,
                "link": f"https://www.deezer.com/track/{1000 + i}",
                "duration": 200,
                "track_position": i,
                "disk_number": 1,
                "artist": {"id": aid, "name": f"Artist {aid}"},
            }
            for i, aid in enumerate(track_artist_ids, start=1)
        ]
    }
    return album, tracks


class DeezerPluginTest(PluginTestCase):
    plugin = "deezer"

    def setUp(self):
        super().setUp()
        self.deezer = deezer.DeezerPlugin()

    def _mock_album(self, album_id, album, tracks):
        responses.add(
            responses.GET,
            f"{deezer.DeezerPlugin.album_url}{album_id}",
            json=album,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{deezer.DeezerPlugin.album_url}{album_id}/tracks",
            json=tracks,
            status=200,
        )

    @responses.activate
    def test_compilation_with_non_va_album_artist(self):
        # Album credited to a single "main" artist that performs on only one
        # of many tracks: this is a compilation and should be flagged as VA.
        album, tracks = _album_payload(
            album_artist_id=100, track_artist_ids=[100, 200, 300, 400, 500, 600]
        )
        self._mock_album("1", album, tracks)

        album_info = self.deezer.album_for_id("1")

        assert album_info is not None
        assert album_info.va is True
        assert album_info.artist == "Various Artists"

    @responses.activate
    def test_single_artist_album_not_va(self):
        # Album whose main artist performs on every track is not a compilation.
        album, tracks = _album_payload(
            album_artist_id=100, track_artist_ids=[100, 100, 100, 100]
        )
        self._mock_album("1", album, tracks)

        album_info = self.deezer.album_for_id("1")

        assert album_info is not None
        assert album_info.va is False
        assert album_info.artist == "Artist 100"
