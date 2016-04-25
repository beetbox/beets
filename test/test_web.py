# -*- coding: utf-8 -*-

"""Tests for the 'web' plugin"""

from __future__ import division, absolute_import, print_function

from test._common import unittest
from test import _common
import json
import beetsplug
from beets.library import Item, Album
beetsplug.__path__ = ['./beetsplug', '../beetsplug']  # noqa
from beetsplug import web


class WebPluginTest(_common.LibTestCase):

    def setUp(self):
        super(WebPluginTest, self).setUp()

        # Add fixtures
        for track in self.lib.items():
            track.remove()
        self.lib.add(Item(title=u'title', path='', id=1))
        self.lib.add(Item(title=u'another title', path='', id=2))
        self.lib.add(Album(album=u'album', id=3))
        self.lib.add(Album(album=u'another album', id=4))

        web.app.config['TESTING'] = True
        web.app.config['lib'] = self.lib
        self.client = web.app.test_client()

    def test_get_all_items(self):
        response = self.client.get('/item/')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['items']), 2)

    def test_get_single_item_by_id(self):
        response = self.client.get('/item/1')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['id'], 1)
        self.assertEqual(response.json['title'], u'title')

    def test_get_multiple_items_by_id(self):
        response = self.client.get('/item/1,2')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['items']), 2)
        response_titles = [item['title'] for item in response.json['items']]
        self.assertItemsEqual(response_titles, [u'title', u'another title'])

    def test_get_single_item_not_found(self):
        response = self.client.get('/item/3')
        self.assertEqual(response.status_code, 404)

    def test_get_item_empty_query(self):
        response = self.client.get('/item/query/')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['items']), 2)

    def test_get_simple_item_query(self):
        response = self.client.get('/item/query/another')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['title'],
                         u'another title')

    def test_get_all_albums(self):
        response = self.client.get('/album/')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        response_albums = [album['album'] for album in response.json['albums']]
        self.assertItemsEqual(response_albums, [u'album', u'another album'])

    def test_get_single_album_by_id(self):
        response = self.client.get('/album/2')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['id'], 2)
        self.assertEqual(response.json['album'], u'another album')

    def test_get_multiple_albums_by_id(self):
        response = self.client.get('/album/1,2')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        response_albums = [album['album'] for album in response.json['albums']]
        self.assertItemsEqual(response_albums, [u'album', u'another album'])

    def test_get_album_empty_query(self):
        response = self.client.get('/album/query/')
        response.json = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['albums']), 2)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
