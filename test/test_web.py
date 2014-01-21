"""Tests for the 'web' plugin"""

from _common import unittest
import _common
import json
import beets
import beetsplug
beetsplug.__path__ = ['./beetsplug', '../beetsplug']
from beetsplug import web


class WebPluginTest(_common.LibTestCase):

    def setUp(self):
        super(WebPluginTest, self).setUp()

        # Add fixtures
        self.lib.add(beets.library.Item(
            title =            u'another title',
            path =             'somepath' + str(_common._item_ident)))
        self.lib.add(beets.library.Album())
        self.lib.add(beets.library.Album())

        web.app.config['TESTING'] = True
        web.app.config['lib'] = self.lib
        self.client = web.app.test_client()

    def test_get_item(self):
        response = self.client.get('/item/')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['items']), 2)

    def test_get_item_empty_query(self):
        response = self.client.get('/item/query/')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['items']), 2)

    def test_get_album(self):
        response = self.client.get('/album/')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['albums']), 2)

    def test_get_album_empty_query(self):
        response = self.client.get('/album/query/')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['albums']), 2)

    


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
