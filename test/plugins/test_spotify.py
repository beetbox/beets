"""Tests for the 'spotify' plugin"""

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
            f"{spotify.SpotifyPlugin.track_url}6NPVjNh8Jhru9xOmyQigds",
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
            f"{spotify.SpotifyPlugin.track_url}6sjZfVJworBX6TqyjkxIJ1",
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
