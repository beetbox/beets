# -*- coding: utf-8 -*-

"""Tests for the 'web' plugin"""

from __future__ import division, absolute_import, print_function

import json
import unittest
import os.path
from six import assertCountEqual

from test import _common
from beets.library import Item, Album
from beetsplug import web


class WebPluginTest(_common.LibTestCase):

    def setUp(self):
        super(WebPluginTest, self).setUp()

        # Add fixtures
        for track in self.lib.items():
            track.remove()
        self.lib.add(Item(title=u'title', path='/path_1', id=1))
        self.lib.add(Item(title=u'another title', path='/path_2', id=2))
        self.lib.add(Album(album=u'album', id=3))
        self.lib.add(Album(album=u'another album', id=4))

        web.app.config['TESTING'] = True
        web.app.config['lib'] = self.lib
        web.app.config['INCLUDE_PATHS'] = False
        self.client = web.app.test_client()

    def test_config_include_paths_true(self):
        web.app.config['INCLUDE_PATHS'] = True
        response = self.client.get('/item/1')
        response.json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['path'], u'/path_1')

    def test_config_include_paths_false(self):
        web.app.config['INCLUDE_PATHS'] = False
        response = self.client.get('/item/1')
        response.json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('path', response.json)

    def test_get_all_items(self):
        response = self.client.get('/item/')
        response.json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['items']), 2)

    def test_get_single_item_by_id(self):
        response = self.client.get('/item/1')
        response.json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['id'], 1)
        self.assertEqual(response.json['title'], u'title')

    def test_get_multiple_items_by_id(self):
        response = self.client.get('/item/1,2')
        response.json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['items']), 2)
        response_titles = [item['title'] for item in response.json['items']]
        assertCountEqual(self, response_titles, [u'title', u'another title'])

    def test_get_single_item_not_found(self):
        response = self.client.get('/item/3')
        self.assertEqual(response.status_code, 404)

    def test_get_single_item_by_path(self):
        data_path = os.path.join(_common.RSRC, b'full.mp3')
        self.lib.add(Item.from_path(data_path))
        response = self.client.get('/item/path/' + data_path.decode('utf-8'))
        response.json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['title'], u'full')

    def test_get_single_item_by_path_not_found_if_not_in_library(self):
        data_path = os.path.join(_common.RSRC, b'full.mp3')
        # data_path points to a valid file, but we have not added the file
        # to the library.
        response = self.client.get('/item/path/' + data_path.decode('utf-8'))

        self.assertEqual(response.status_code, 404)

    def test_get_item_empty_query(self):
        response = self.client.get('/item/query/')
        response.json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['items']), 2)

    def test_get_simple_item_query(self):
        response = self.client.get('/item/query/another')
        response.json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['title'],
                         u'another title')

    def test_get_all_albums(self):
        response = self.client.get('/album/')
        response.json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        response_albums = [album['album'] for album in response.json['albums']]
        assertCountEqual(self, response_albums, [u'album', u'another album'])

    def test_get_single_album_by_id(self):
        response = self.client.get('/album/2')
        response.json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['id'], 2)
        self.assertEqual(response.json['album'], u'another album')

    def test_get_multiple_albums_by_id(self):
        response = self.client.get('/album/1,2')
        response.json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        response_albums = [album['album'] for album in response.json['albums']]
        assertCountEqual(self, response_albums, [u'album', u'another album'])

    def test_get_album_empty_query(self):
        response = self.client.get('/album/query/')
        response.json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['albums']), 2)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
