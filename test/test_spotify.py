# -*- coding: utf-8 -*-

"""Tests for the 'spotify' plugin"""

from __future__ import division, absolute_import, print_function

import os
import responses
import unittest

from test import _common
from beets import config
from beets.library import Item
from beetsplug import spotify
from test.helper import TestHelper
from six.moves.urllib.parse import parse_qs, urlparse


class ArgumentsMock(object):
    def __init__(self, mode, show_failures):
        self.mode = mode
        self.show_failures = show_failures
        self.verbose = 1


def _params(url):
    """Get the query parameters from a URL."""
    return parse_qs(urlparse(url).query)


class SpotifyPluginTest(_common.TestCase, TestHelper):

    def setUp(self):
        config.clear()
        self.setup_beets()
        self.spotify = spotify.SpotifyPlugin()
        opts = ArgumentsMock("list", False)
        self.spotify.parse_opts(opts)

    def tearDown(self):
        self.teardown_beets()

    def test_args(self):
        opts = ArgumentsMock("fail", True)
        self.assertEqual(False, self.spotify.parse_opts(opts))
        opts = ArgumentsMock("list", False)
        self.assertEqual(True, self.spotify.parse_opts(opts))

    def test_empty_query(self):
        self.assertEqual(None, self.spotify.query_spotify(self.lib, u"1=2"))

    @responses.activate
    def test_missing_request(self):
        json_file = os.path.join(_common.RSRC, b'spotify',
                                 b'missing_request.json')
        with open(json_file, 'rb') as f:
            response_body = f.read()

        responses.add(responses.GET, 'https://api.spotify.com/v1/search',
                      body=response_body, status=200,
                      content_type='application/json')
        item = Item(
            mb_trackid=u'01234',
            album=u'lkajsdflakjsd',
            albumartist=u'ujydfsuihse',
            title=u'duifhjslkef',
            length=10
        )
        item.add(self.lib)
        self.assertEqual([], self.spotify.query_spotify(self.lib, u""))

        params = _params(responses.calls[0].request.url)
        self.assertEqual(
            params['q'],
            [u'duifhjslkef album:lkajsdflakjsd artist:ujydfsuihse'],
        )
        self.assertEqual(params['type'], [u'track'])

    @responses.activate
    def test_track_request(self):

        json_file = os.path.join(_common.RSRC, b'spotify',
                                 b'track_request.json')
        with open(json_file, 'rb') as f:
            response_body = f.read()

        responses.add(responses.GET, 'https://api.spotify.com/v1/search',
                      body=response_body, status=200,
                      content_type='application/json')
        item = Item(
            mb_trackid=u'01234',
            album=u'Despicable Me 2',
            albumartist=u'Pharrell Williams',
            title=u'Happy',
            length=10
        )
        item.add(self.lib)
        results = self.spotify.query_spotify(self.lib, u"Happy")
        self.assertEqual(1, len(results))
        self.assertEqual(u"6NPVjNh8Jhru9xOmyQigds", results[0]['id'])
        self.spotify.output_results(results)

        params = _params(responses.calls[0].request.url)
        self.assertEqual(
            params['q'],
            [u'Happy album:Despicable Me 2 artist:Pharrell Williams'],
        )
        self.assertEqual(params['type'], [u'track'])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
