# -*- coding: utf-8 -*-

"""Tests for the 'spotify' plugin"""

from __future__ import division, absolute_import, print_function

from test import _common
import responses
from test._common import unittest
from beets import config
from beets.library import Item
from beetsplug import spotify
from test.helper import TestHelper
import urlparse


class ArgumentsMock(object):
    def __init__(self, mode, show_failures):
        self.mode = mode
        self.show_failures = show_failures
        self.verbose = 1


def _params(url):
    """Get the query parameters from a URL."""
    return urlparse.parse_qs(urlparse.urlparse(url).query)


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
        response_body = bytes(
            '{'
            '"tracks" : {'
            '"href" : "https://api.spotify.com/v1/search?query=duifhjslkef'
            '+album%3Alkajsdflakjsd+artist%3A&offset=0&limit=20&type=track",'
            '"items" : [ ],'
            '"limit" : 20,'
            '"next" : null,'
            '"offset" : 0,'
            '"previous" : null,'
            '"total" : 0'
            '}'
            '}'
        )
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
        response_body = bytes(
            '{'
            '"tracks" : {'
            '"href" : "https://api.spotify.com/v1/search?query=Happy+album%3A'
            'Despicable+Me+2+artist%3APharrell+Williams&offset=0&limit=20'
            '&type=track",'
            '"items" : [ {'
            '"album" : {'
            '"album_type" : "compilation",'
            '"available_markets" : [ "AD", "AR", "AT", "AU", "BE", "BG",'
            '"BO", "BR", "CA", "CH", "CL", "CO",'
            '"CR", "CY", "CZ", "DE", "DK", "DO",'
            '"EC", "EE", "ES", "FI", "FR", "GB",'
            '"GR", "GT", "HK", "HN", "HU", "IE",'
            '"IS", "IT", "LI", "LT", "LU", "LV",'
            '"MC", "MT", "MX", "MY", "NI", "NL",'
            '"NO", "NZ", "PA", "PE", "PH", "PL",'
            '"PT", "PY", "RO", "SE", "SG", "SI",'
            '"SK", "SV", "TR", "TW", "US", "UY" ],'
            '"external_urls" : {'
            '"spotify" : "https://open.spotify.com/album/'
            '5l3zEmMrOhOzG8d8s83GOL"'
            '},'
            '"href" : "https://api.spotify.com/v1/albums/'
            '5l3zEmMrOhOzG8d8s83GOL",'
            '"id" : "5l3zEmMrOhOzG8d8s83GOL",'
            '"images" : [ {'
            '"height" : 640,'
            '"url" : "https://i.scdn.co/image/cb7905340c132365bb'
            'aee3f17498f062858382e8",'
            '"width" : 640'
            '}, {'
            '"height" : 300,'
            '"url" : "https://i.scdn.co/image/af369120f0b20099'
            'd6784ab31c88256113f10ffb",'
            '"width" : 300'
            '}, {'
            '"height" : 64,'
            '"url" : "https://i.scdn.co/image/'
            '9dad385ddf2e7db0bef20cec1fcbdb08689d9ae8",'
            '"width" : 64'
            '} ],'
            '"name" : "Despicable Me 2 (Original Motion Picture Soundtrack)",'
            '"type" : "album",'
            '"uri" : "spotify:album:5l3zEmMrOhOzG8d8s83GOL"'
            '},'
            '"artists" : [ {'
            '"external_urls" : {'
            '"spotify" : "https://open.spotify.com/artist/'
            '2RdwBSPQiwcmiDo9kixcl8"'
            '},'
            '"href" : "https://api.spotify.com/v1/artists/'
            '2RdwBSPQiwcmiDo9kixcl8",'
            '"id" : "2RdwBSPQiwcmiDo9kixcl8",'
            '"name" : "Pharrell Williams",'
            '"type" : "artist",'
            '"uri" : "spotify:artist:2RdwBSPQiwcmiDo9kixcl8"'
            '} ],'
            '"available_markets" : [ "AD", "AR", "AT", "AU", "BE", "BG", "BO",'
            '"BR", "CA", "CH", "CL", "CO", "CR", "CY",'
            '"CZ", "DE", "DK", "DO", "EC", "EE", "ES",'
            '"FI", "FR", "GB", "GR", "GT", "HK", "HN",'
            '"HU", "IE", "IS", "IT", "LI", "LT", "LU",'
            '"LV", "MC", "MT", "MX", "MY", "NI", "NL",'
            '"NO", "NZ", "PA", "PE", "PH", "PL", "PT",'
            '"PY", "RO", "SE", "SG", "SI", "SK", "SV",'
            '"TR", "TW", "US", "UY" ],'
            '"disc_number" : 1,'
            '"duration_ms" : 233305,'
            '"explicit" : false,'
            '"external_ids" : {'
            '"isrc" : "USQ4E1300686"'
            '},'
            '"external_urls" : {'
            '"spotify" : "https://open.spotify.com/track/'
            '6NPVjNh8Jhru9xOmyQigds"'
            '},'
            '"href" : "https://api.spotify.com/v1/tracks/'
            '6NPVjNh8Jhru9xOmyQigds",'
            '"id" : "6NPVjNh8Jhru9xOmyQigds",'
            '"name" : "Happy",'
            '"popularity" : 89,'
            '"preview_url" : "https://p.scdn.co/mp3-preview/'
            '6b00000be293e6b25f61c33e206a0c522b5cbc87",'
            '"track_number" : 4,'
            '"type" : "track",'
            '"uri" : "spotify:track:6NPVjNh8Jhru9xOmyQigds"'
            '} ],'
            '"limit" : 20,'
            '"next" : null,'
            '"offset" : 0,'
            '"previous" : null,'
            '"total" : 1'
            '}'
            '}'
        )
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

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
