"""Tests for the 'spotify' plugin"""

import json
import os
from urllib.parse import parse_qs, urlparse

import responses

from beets.library import Item
from beets.test import _common
from beets.test.helper import PluginTestCase
from beetsplug import spotify


class ArgumentsMock:
    def __init__(self, mode, show_failures):
        self.mode = mode
        self.show_failures = show_failures
        self.verbose = 1


def _params(url):
    """Get the query parameters from a URL."""
    return parse_qs(urlparse(url).query)


class SpotifyPluginTest(PluginTestCase):
    plugin = "spotify"

    @responses.activate
    def setUp(self):
        responses.add(
            responses.POST,
            spotify.SpotifyPlugin.oauth_token_url,
            status=200,
            json={
                "access_token": "3XyiC3raJySbIAV5LVYj1DaWbcocNi3LAJTNXRnYY"
                "GVUl6mbbqXNhW3YcZnQgYXNWHFkVGSMlc0tMuvq8CF",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "",
            },
        )
        super().setUp()
        self.spotify = spotify.SpotifyPlugin()
        opts = ArgumentsMock("list", False)
        self.spotify._parse_opts(opts)

    def test_args(self):
        opts = ArgumentsMock("fail", True)
        assert not self.spotify._parse_opts(opts)
        opts = ArgumentsMock("list", False)
        assert self.spotify._parse_opts(opts)

    def test_empty_query(self):
        assert self.spotify._match_library_tracks(self.lib, "1=2") is None

    @responses.activate
    def test_missing_request(self):
        json_file = os.path.join(
            _common.RSRC, b"spotify", b"missing_request.json"
        )
        with open(json_file, "rb") as f:
            response_body = f.read()

        responses.add(
            responses.GET,
            spotify.SpotifyPlugin.search_url,
            body=response_body,
            status=200,
            content_type="application/json",
        )
        item = Item(
            mb_trackid="01234",
            album="lkajsdflakjsd",
            albumartist="ujydfsuihse",
            title="duifhjslkef",
            length=10,
        )
        item.add(self.lib)
        assert [] == self.spotify._match_library_tracks(self.lib, "")

        params = _params(responses.calls[0].request.url)
        query = params["q"][0]
        assert "duifhjslkef" in query
        assert "artist:'ujydfsuihse'" in query
        assert "album:'lkajsdflakjsd'" in query
        assert params["type"] == ["track"]

    @responses.activate
    def test_track_request(self):
        json_file = os.path.join(
            _common.RSRC, b"spotify", b"track_request.json"
        )
        with open(json_file, "rb") as f:
            response_body = f.read()

        responses.add(
            responses.GET,
            spotify.SpotifyPlugin.search_url,
            body=response_body,
            status=200,
            content_type="application/json",
        )
        item = Item(
            mb_trackid="01234",
            album="Despicable Me 2",
            albumartist="Pharrell Williams",
            title="Happy",
            length=10,
        )
        item.add(self.lib)
        results = self.spotify._match_library_tracks(self.lib, "Happy")
        assert 1 == len(results)
        assert "6NPVjNh8Jhru9xOmyQigds" == results[0]["id"]
        self.spotify._output_match_results(results)

        params = _params(responses.calls[0].request.url)
        query = params["q"][0]
        assert "Happy" in query
        assert "artist:'Pharrell Williams'" in query
        assert "album:'Despicable Me 2'" in query
        assert params["type"] == ["track"]

    @responses.activate
    def test_track_for_id(self):
        """Tests if plugin is able to fetch a track by its Spotify ID"""

        # Mock the Spotify 'Get Track' call
        json_file = os.path.join(_common.RSRC, b"spotify", b"track_info.json")
        with open(json_file, "rb") as f:
            response_body = f.read()

        responses.add(
            responses.GET,
            f"{spotify.SpotifyPlugin.track_url}/6NPVjNh8Jhru9xOmyQigds",
            body=response_body,
            status=200,
            content_type="application/json",
        )

        # Mock the Spotify 'Get Album' call
        json_file = os.path.join(_common.RSRC, b"spotify", b"album_info.json")
        with open(json_file, "rb") as f:
            response_body = f.read()

        responses.add(
            responses.GET,
            f"{spotify.SpotifyPlugin.album_url}5l3zEmMrOhOzG8d8s83GOL",
            body=response_body,
            status=200,
            content_type="application/json",
        )

        # Mock the Spotify 'Search' call
        json_file = os.path.join(
            _common.RSRC, b"spotify", b"track_request.json"
        )
        with open(json_file, "rb") as f:
            response_body = f.read()

        responses.add(
            responses.GET,
            spotify.SpotifyPlugin.search_url,
            body=response_body,
            status=200,
            content_type="application/json",
        )

        track_info = self.spotify.track_for_id("6NPVjNh8Jhru9xOmyQigds")
        item = Item(
            mb_trackid=track_info.track_id,
            albumartist=track_info.artist,
            title=track_info.title,
            length=track_info.length,
        )
        item.add(self.lib)

        results = self.spotify._match_library_tracks(self.lib, "Happy")
        assert 1 == len(results)
        assert "6NPVjNh8Jhru9xOmyQigds" == results[0]["id"]

    @responses.activate
    def test_japanese_track(self):
        """Ensure non-ASCII characters remain unchanged in search queries"""

        # Path to the mock JSON file for the Japanese track
        json_file = os.path.join(
            _common.RSRC, b"spotify", b"japanese_track_request.json"
        )

        # Load the mock JSON response
        with open(json_file, "rb") as f:
            response_body = f.read()

        # Mock Spotify Search API response
        responses.add(
            responses.GET,
            spotify.SpotifyPlugin.search_url,
            body=response_body,
            status=200,
            content_type="application/json",
        )

        # Create a mock item with Japanese metadata
        item = Item(
            mb_trackid="56789",
            album="盗作",
            albumartist="ヨルシカ",
            title="思想犯",
            length=10,
        )
        item.add(self.lib)

        # Search without ascii encoding

        with self.configure_plugin(
            {
                "search_query_ascii": False,
            }
        ):
            assert self.spotify.config["search_query_ascii"].get() is False
            # Call the method to match library tracks
            results = self.spotify._match_library_tracks(self.lib, item.title)

            # Assertions to verify results
            assert results is not None
            assert 1 == len(results)
            assert results[0]["name"] == item.title
            assert results[0]["artists"][0]["name"] == item.albumartist
            assert results[0]["album"]["name"] == item.album

            # Verify search query parameters
            params = _params(responses.calls[0].request.url)
            query = params["q"][0]
            assert item.title in query
            assert f"artist:'{item.albumartist}'" in query
            assert f"album:'{item.album}'" in query
            assert not query.isascii()

        # Is not found in the library if ascii encoding is enabled
        with self.configure_plugin(
            {
                "search_query_ascii": True,
            }
        ):
            assert self.spotify.config["search_query_ascii"].get() is True
            results = self.spotify._match_library_tracks(self.lib, item.title)
            params = _params(responses.calls[1].request.url)
            query = params["q"][0]

            assert query.isascii()

    @responses.activate
    def test_multiartist_album_and_track(self):
        """Tests if plugin is able to map multiple artists in an album and
        track info correctly"""

        # Mock the Spotify 'Get Album' call
        json_file = os.path.join(
            _common.RSRC, b"spotify", b"multiartist_album.json"
        )
        with open(json_file, "rb") as f:
            album_response_body = f.read()

        responses.add(
            responses.GET,
            f"{spotify.SpotifyPlugin.album_url}0yhKyyjyKXWUieJ4w1IAEa",
            body=album_response_body,
            status=200,
            content_type="application/json",
        )

        # Mock the Spotify 'Get Track' call
        json_file = os.path.join(
            _common.RSRC, b"spotify", b"multiartist_track.json"
        )
        with open(json_file, "rb") as f:
            track_response_body = f.read()

        responses.add(
            responses.GET,
            f"{spotify.SpotifyPlugin.track_url}/6sjZfVJworBX6TqyjkxIJ1",
            body=track_response_body,
            status=200,
            content_type="application/json",
        )

        album_info = self.spotify.album_for_id("0yhKyyjyKXWUieJ4w1IAEa")
        assert album_info is not None
        assert album_info.artist == "Project Skylate, Sugar Shrill"
        assert album_info.artists == ["Project Skylate", "Sugar Shrill"]
        assert album_info.artist_id == "6m8MRXIVKb6wQaPlBIDMr1"
        assert album_info.artists_ids == [
            "6m8MRXIVKb6wQaPlBIDMr1",
            "4kkAIoQmNT5xEoNH5BuQLe",
        ]

        assert len(album_info.tracks) == 1
        assert album_info.tracks[0].artist == "Foo, Bar"
        assert album_info.tracks[0].artists == ["Foo", "Bar"]
        assert album_info.tracks[0].artist_id == "12345"
        assert album_info.tracks[0].artists_ids == ["12345", "67890"]

        track_info = self.spotify.track_for_id("6sjZfVJworBX6TqyjkxIJ1")
        assert track_info is not None
        assert track_info.artist == "Foo, Bar"
        assert track_info.artists == ["Foo", "Bar"]
        assert track_info.artist_id == "12345"
        assert track_info.artists_ids == ["12345", "67890"]

    @responses.activate
    def test_get_track_details_by_id_chunks_requests(self):
        ids_per_request = []

        def callback(request):
            ids = _params(request.url)["ids"][0].split(",")
            ids_per_request.append(len(ids))
            return (
                200,
                {"Content-Type": "application/json"},
                json.dumps(
                    {
                        "tracks": [
                            {
                                "id": track_id,
                                "popularity": 50,
                                "external_ids": {},
                            }
                            for track_id in ids
                        ]
                    }
                ),
            )

        responses.add_callback(
            responses.GET,
            spotify.SpotifyPlugin.track_url,
            callback=callback,
            content_type="application/json",
        )

        track_ids = [f"track-{idx}" for idx in range(51)]
        track_info = self.spotify.get_track_details_by_id(track_ids)

        assert len(track_info) == 51
        assert ids_per_request == [50, 1]

    @responses.activate
    def test_fetch_info_uses_batch_endpoints(self):
        responses.add(
            responses.GET,
            spotify.SpotifyPlugin.track_url,
            status=200,
            json={
                "tracks": [
                    {
                        "id": "id-1",
                        "popularity": 10,
                        "external_ids": {
                            "isrc": "isrc-1",
                            "ean": "ean-1",
                            "upc": "upc-1",
                        },
                    },
                    {
                        "id": "id-2",
                        "popularity": 20,
                        "external_ids": {
                            "isrc": "isrc-2",
                            "ean": "ean-2",
                            "upc": "upc-2",
                        },
                    },
                    {
                        "id": "id-3",
                        "popularity": 30,
                        "external_ids": {
                            "isrc": "isrc-3",
                            "ean": "ean-3",
                            "upc": "upc-3",
                        },
                    },
                ]
            },
            content_type="application/json",
        )
        responses.add(
            responses.GET,
            spotify.SpotifyPlugin.audio_features_url,
            status=200,
            json={
                "audio_features": [
                    {"id": "id-1", "tempo": 100.1, "energy": 0.4},
                    {"id": "id-2", "tempo": 110.2, "energy": 0.5},
                    {"id": "id-3", "tempo": 120.3, "energy": 0.6},
                ]
            },
            content_type="application/json",
        )

        items = []
        for idx in range(1, 4):
            item = Item(title=f"Track {idx}", artist="Artist", length=10)
            item.add(self.lib)
            item["spotify_track_id"] = f"id-{idx}"
            items.append(item)

        self.spotify._fetch_info(items, write=False, force=True)

        get_calls = [
            call for call in responses.calls if call.request.method == "GET"
        ]
        batch_track_calls = [
            call
            for call in get_calls
            if urlparse(call.request.url).path == "/v1/tracks"
        ]
        single_track_calls = [
            call
            for call in get_calls
            if urlparse(call.request.url).path.startswith("/v1/tracks/")
        ]
        batch_audio_calls = [
            call
            for call in get_calls
            if urlparse(call.request.url).path == "/v1/audio-features"
        ]
        single_audio_calls = [
            call
            for call in get_calls
            if urlparse(call.request.url).path.startswith("/v1/audio-features/")
        ]

        assert len(batch_track_calls) == 1
        assert len(single_track_calls) == 0
        assert len(batch_audio_calls) == 1
        assert len(single_audio_calls) == 0

        assert items[0]["spotify_track_popularity"] == 10
        assert items[1]["spotify_track_popularity"] == 20
        assert items[2]["spotify_track_popularity"] == 30

        assert items[0]["spotify_tempo"] == 100.1
        assert items[1]["spotify_tempo"] == 110.2
        assert items[2]["spotify_tempo"] == 120.3

    @responses.activate
    def test_fetch_info_deduplicates_batch_ids(self):
        seen_track_ids = []
        seen_audio_ids = []

        def track_callback(request):
            ids = _params(request.url)["ids"][0].split(",")
            seen_track_ids.append(ids)
            return (
                200,
                {"Content-Type": "application/json"},
                json.dumps(
                    {
                        "tracks": [
                            {
                                "id": track_id,
                                "popularity": 50,
                                "external_ids": {},
                            }
                            for track_id in ids
                        ]
                    }
                ),
            )

        def audio_callback(request):
            ids = _params(request.url)["ids"][0].split(",")
            seen_audio_ids.append(ids)
            return (
                200,
                {"Content-Type": "application/json"},
                json.dumps(
                    {
                        "audio_features": [
                            {"id": track_id, "tempo": 100.0} for track_id in ids
                        ]
                    }
                ),
            )

        responses.add_callback(
            responses.GET,
            spotify.SpotifyPlugin.track_url,
            callback=track_callback,
            content_type="application/json",
        )
        responses.add_callback(
            responses.GET,
            spotify.SpotifyPlugin.audio_features_url,
            callback=audio_callback,
            content_type="application/json",
        )

        items = []
        for idx in range(2):
            item = Item(title=f"Track {idx}", artist="Artist", length=10)
            item.add(self.lib)
            item["spotify_track_id"] = "shared-id"
            items.append(item)

        self.spotify._fetch_info(items, write=False, force=True)

        assert seen_track_ids == [["shared-id"]]
        assert seen_audio_ids == [["shared-id"]]
        assert items[0]["spotify_track_popularity"] == 50
        assert items[1]["spotify_track_popularity"] == 50

    @responses.activate
    def test_track_audio_features_batch_disables_on_403(self):
        responses.add(
            responses.GET,
            spotify.SpotifyPlugin.audio_features_url,
            status=403,
            json={"error": {"status": 403}},
            content_type="application/json",
        )

        assert self.spotify.track_audio_features_batch(["id-1"]) == {}
        assert self.spotify.audio_features_available is False
        assert self.spotify.track_audio_features_batch(["id-2"]) == {}
        assert len(responses.calls) == 1

    @responses.activate
    def test_track_audio_features_batch_keeps_partial_results_on_api_error(
        self,
    ):
        def callback(request):
            ids = _params(request.url)["ids"][0].split(",")
            if "track-100" in ids:
                return (
                    502,
                    {"Content-Type": "application/json"},
                    json.dumps({"error": {"status": 502}}),
                )
            return (
                200,
                {"Content-Type": "application/json"},
                json.dumps(
                    {
                        "audio_features": [
                            {"id": track_id, "tempo": 100.0} for track_id in ids
                        ]
                    }
                ),
            )

        responses.add_callback(
            responses.GET,
            spotify.SpotifyPlugin.audio_features_url,
            callback=callback,
            content_type="application/json",
        )

        track_ids = [f"track-{idx}" for idx in range(201)]
        features = self.spotify.track_audio_features_batch(track_ids)

        assert "track-0" in features
        assert "track-99" in features
        assert "track-100" not in features
        assert "track-199" not in features
        assert "track-200" in features
