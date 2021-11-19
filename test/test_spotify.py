"""Tests for the 'spotify' plugin"""


import os
import responses
import unittest

from test import _common
from beets import config
from beets.library import Item
from beetsplug import spotify
from test.helper import TestHelper
from six.moves.urllib.parse import parse_qs, urlparse


class ArgumentsMock:
    def __init__(self, mode, show_failures):
        self.mode = mode
        self.show_failures = show_failures
        self.verbose = 1


def _params(url):
    """Get the query parameters from a URL."""
    return parse_qs(urlparse(url).query)


class SpotifyPluginTest(_common.TestCase, TestHelper):
    @responses.activate
    def setUp(self):
        config.clear()
        self.setup_beets()
        responses.add(
            responses.POST,
            spotify.SpotifyPlugin.oauth_token_url,
            status=200,
            json={
                'access_token': '3XyiC3raJySbIAV5LVYj1DaWbcocNi3LAJTNXRnYY'
                'GVUl6mbbqXNhW3YcZnQgYXNWHFkVGSMlc0tMuvq8CF',
                'token_type': 'Bearer',
                'expires_in': 3600,
                'scope': '',
            },
        )
        self.spotify = spotify.SpotifyPlugin()
        opts = ArgumentsMock("list", False)
        self.spotify._parse_opts(opts)

    def tearDown(self):
        self.teardown_beets()

    def test_args(self):
        opts = ArgumentsMock("fail", True)
        self.assertEqual(False, self.spotify._parse_opts(opts))
        opts = ArgumentsMock("list", False)
        self.assertEqual(True, self.spotify._parse_opts(opts))

    def test_empty_query(self):
        self.assertEqual(
            None, self.spotify._match_library_tracks(self.lib, "1=2")
        )

    @responses.activate
    def test_missing_request(self):
        json_file = os.path.join(
            _common.RSRC, b'spotify', b'missing_request.json'
        )
        with open(json_file, 'rb') as f:
            response_body = f.read()

        responses.add(
            responses.GET,
            spotify.SpotifyPlugin.search_url,
            body=response_body,
            status=200,
            content_type='application/json',
        )
        item = Item(
            mb_trackid='01234',
            album='lkajsdflakjsd',
            albumartist='ujydfsuihse',
            title='duifhjslkef',
            length=10,
        )
        item.add(self.lib)
        self.assertEqual([], self.spotify._match_library_tracks(self.lib, ""))

        params = _params(responses.calls[0].request.url)
        query = params['q'][0]
        self.assertIn('duifhjslkef', query)
        self.assertIn('artist:ujydfsuihse', query)
        self.assertIn('album:lkajsdflakjsd', query)
        self.assertEqual(params['type'], ['track'])

    @responses.activate
    def test_track_request(self):
        json_file = os.path.join(
            _common.RSRC, b'spotify', b'track_request.json'
        )
        with open(json_file, 'rb') as f:
            response_body = f.read()

        responses.add(
            responses.GET,
            spotify.SpotifyPlugin.search_url,
            body=response_body,
            status=200,
            content_type='application/json',
        )
        item = Item(
            mb_trackid='01234',
            album='Despicable Me 2',
            albumartist='Pharrell Williams',
            title='Happy',
            length=10,
        )
        item.add(self.lib)
        results = self.spotify._match_library_tracks(self.lib, "Happy")
        self.assertEqual(1, len(results))
        self.assertEqual("6NPVjNh8Jhru9xOmyQigds", results[0]['id'])
        self.spotify._output_match_results(results)

        params = _params(responses.calls[0].request.url)
        query = params['q'][0]
        self.assertIn('Happy', query)
        self.assertIn('artist:Pharrell Williams', query)
        self.assertIn('album:Despicable Me 2', query)
        self.assertEqual(params['type'], ['track'])

    @responses.activate
    def test_track_for_id(self):
        """Tests if plugin is able to fetch a track by its Spotify ID"""

        # Mock the Spotify 'Get Track' call
        json_file = os.path.join(
            _common.RSRC, b'spotify', b'track_info.json'
        )
        with open(json_file, 'rb') as f:
            response_body = f.read()

        responses.add(
            responses.GET,
            spotify.SpotifyPlugin.track_url + '6NPVjNh8Jhru9xOmyQigds',
            body=response_body,
            status=200,
            content_type='application/json',
        )

        # Mock the Spotify 'Get Album' call
        json_file = os.path.join(
            _common.RSRC, b'spotify', b'album_info.json'
        )
        with open(json_file, 'rb') as f:
            response_body = f.read()

        responses.add(
            responses.GET,
            spotify.SpotifyPlugin.album_url + '5l3zEmMrOhOzG8d8s83GOL',
            body=response_body,
            status=200,
            content_type='application/json',
        )

        # Mock the Spotify 'Search' call
        json_file = os.path.join(
            _common.RSRC, b'spotify', b'track_request.json'
        )
        with open(json_file, 'rb') as f:
            response_body = f.read()

        responses.add(
            responses.GET,
            spotify.SpotifyPlugin.search_url,
            body=response_body,
            status=200,
            content_type='application/json',
        )

        track_info = self.spotify.track_for_id('6NPVjNh8Jhru9xOmyQigds')
        item = Item(
            mb_trackid=track_info.track_id,
            albumartist=track_info.artist,
            title=track_info.title,
            length=track_info.length
        )
        item.add(self.lib)

        results = self.spotify._match_library_tracks(self.lib, "Happy")
        self.assertEqual(1, len(results))
        self.assertEqual("6NPVjNh8Jhru9xOmyQigds", results[0]['id'])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
