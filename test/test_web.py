# -*- coding: utf-8 -*-

"""Tests for the 'web' plugin"""

from __future__ import division, absolute_import, print_function

import json
import unittest
import os.path
from six import assertCountEqual

import beets.library
from test import _common
from beets.library import Item, Album
from beetsplug import web

#from mock import patch
from beets import logging

class WebPluginTest(_common.LibTestCase):

    def setUp(self):

        super(WebPluginTest, self).setUp()
        self.log = logging.getLogger('beets.web')
        
        # Add fixtures
        for track in self.lib.items():
            track.remove()

        # Add library elements. Note that self.lib.add overrides any "id=<n>"
        # and assigns the next free id number.
        # The following adds will create items #1, #2 and #3
        self.lib.add(Item(title=u'title',
                      path=os.sep + os.path.join('path_1'),
                      album_id=2,
                      artist='AAA Singers'))
        self.debug_item = self.lib.add(Item(title=u'another title',
                                        path=os.sep + os.path.join('somewhere', 'a'),
                                        artist='AAA Singers'))
        self.lib.add(Item(title=u'and a third',
                      testattr='ABC',
                      path=os.sep + os.path.join('somewhere', 'abc'),
                      album_id=2))
        # The following adds will create albums #1 and #2
        self.lib.add(Album(album=u'album',
                       albumtest='xyz'))
        self.lib.add(Album(album=u'other album',
                       artpath=os.sep
                       + os.path.join('somewhere2', 'art_path_2')))

        web.app.config['TESTING'] = True
        web.app.config['lib'] = self.lib
        web.app.config['INCLUDE_PATHS'] = False
        self.client = web.app.test_client()

    def test_config_include_paths_true(self):
        web.app.config['INCLUDE_PATHS'] = True
        response = self.client.get('/item/1')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(res_json['path'], os.path.join(os.sep, u'path_1'))

        web.app.config['INCLUDE_PATHS'] = False

    def test_config_include_artpaths_true(self):
        web.app.config['INCLUDE_PATHS'] = True
        response = self.client.get('/album/2')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(res_json['artpath'],
                         os.path.join(os.sep, u'somewhere2', u'art_path_2'))

        web.app.config['INCLUDE_PATHS'] = False

    def test_config_include_paths_false(self):
        web.app.config['INCLUDE_PATHS'] = False
        response = self.client.get('/item/1')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('path', res_json)

    def test_config_include_artpaths_false(self):
        web.app.config['INCLUDE_PATHS'] = False
        response = self.client.get('/album/2')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('artpath', res_json)

    def test_get_all_items(self):
        response = self.client.get('/item/')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['items']), 3)

    def test_get_single_item_by_id(self):
        response = self.client.get('/item/1')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(res_json['id'], 1)
        self.assertEqual(res_json['title'], u'title')

    def test_get_multiple_items_by_id(self):
        response = self.client.get('/item/1,2')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['items']), 2)
        response_titles = {item['title'] for item in res_json['items']}
        self.assertEqual(response_titles, {u'title', u'another title'})

    def test_get_single_item_not_found(self):
        response = self.client.get('/item/4')
        self.assertEqual(response.status_code, 404)

    def test_get_single_item_by_path(self):
        data_path = os.path.join(_common.RSRC, b'full.mp3')
        self.lib.add(Item.from_path(data_path))
        response = self.client.get('/item/path/' + data_path.decode('utf-8'))
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(res_json['title'], u'full')

    def test_get_single_item_by_path_not_found_if_not_in_library(self):
        data_path = os.path.join(_common.RSRC, b'full.mp3')
        # data_path points to a valid file, but we have not added the file
        # to the library.
        response = self.client.get('/item/path/' + data_path.decode('utf-8'))

        self.assertEqual(response.status_code, 404)

    def test_get_item_empty_query(self):
        """ testing item query: <empty> """
        response = self.client.get('/item/query/')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['items']), 3)

    def test_get_simple_item_query(self):
        """ testing item query: another """
        response = self.client.get('/item/query/another')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['results']), 1)
        self.assertEqual(res_json['results'][0]['title'],
                         u'another title')

    def test_query_item_string(self):
        """ testing item query: testattr:ABC """
        response = self.client.get('/item/query/testattr%3aABC')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['results']), 1)
        self.assertEqual(res_json['results'][0]['title'],
                         u'and a third')

    def test_query_item_regex(self):
        """ testing item query: testattr::[A-C]+ """
        response = self.client.get('/item/query/testattr%3a%3a[A-C]%2b')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['results']), 1)
        self.assertEqual(res_json['results'][0]['title'],
                         u'and a third')

    def test_query_item_regex_backslash(self):
        # """ testing item query: testattr::\w+ """
        response = self.client.get('/item/query/testattr%3a%3a%5cw%2b')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['results']), 1)
        self.assertEqual(res_json['results'][0]['title'],
                         u'and a third')

    def test_query_item_path(self):
        # """ testing item query: path:\somewhere\a """
        """ Note: path queries are special: the query item must match the path
        from the root all the way to a directory, so this matches 1 item """
        """ Note: filesystem separators in the query must be '\' """
        self.log.info('os.sep: ' + str(os.sep))
        self.log.info('os.join: ' + str(os.path.join('somewhere', 'a')))
        self.log.info('debug item path: ' + str(self.lib.get_item(self.debug_item).path))
      
        response = self.client.get('/item/query/path:\\somewhere\\a')
        res_json = json.loads(response.data.decode('utf-8'))
#        self.log.info('json response: ' + str(response.data))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['results']), 1)
        self.assertEqual(res_json['results'][0]['title'],
                         u'another title')
        # Fail
        self.assertTrue(False)

    def test_get_all_albums(self):
        response = self.client.get('/album/')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        response_albums = [album['album'] for album in res_json['albums']]
        assertCountEqual(self, response_albums, [u'album', u'other album'])

    def test_get_single_album_by_id(self):
        response = self.client.get('/album/2')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(res_json['id'], 2)
        self.assertEqual(res_json['album'], u'other album')

    def test_get_multiple_albums_by_id(self):
        response = self.client.get('/album/1,2')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        response_albums = [album['album'] for album in res_json['albums']]
        assertCountEqual(self, response_albums, [u'album', u'other album'])

    def test_get_album_empty_query(self):
        response = self.client.get('/album/query/')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['albums']), 2)

    def test_get_simple_album_query(self):
        response = self.client.get('/album/query/other')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['results']), 1)
        self.assertEqual(res_json['results'][0]['album'],
                         u'other album')
        self.assertEqual(res_json['results'][0]['id'], 2)

    def test_get_album_details(self):
        response = self.client.get('/album/2?expand')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['items']), 2)
        self.assertEqual(res_json['items'][0]['album'],
                         u'other album')
        self.assertEqual(res_json['items'][1]['album'],
                         u'other album')
        response_track_titles = {item['title'] for item in res_json['items']}
        self.assertEqual(response_track_titles, {u'title', u'and a third'})

    def test_query_album_string(self):
        """ testing query: albumtest:xy """
        response = self.client.get('/album/query/albumtest%3axy')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['results']), 1)
        self.assertEqual(res_json['results'][0]['album'],
                         u'album')

    def test_query_album_artpath_regex(self):
        """ testing query: artpath::art_ """
        response = self.client.get('/album/query/artpath%3a%3aart_')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['results']), 1)
        self.assertEqual(res_json['results'][0]['album'],
                         u'other album')

    def test_query_album_regex_backslash(self):
        # """ testing query: albumtest::\w+ """
        response = self.client.get('/album/query/albumtest%3a%3a%5cw%2b')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(res_json['results']), 1)
        self.assertEqual(res_json['results'][0]['album'],
                         u'album')

    def test_get_stats(self):
        response = self.client.get('/stats')
        res_json = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(res_json['items'], 3)
        self.assertEqual(res_json['albums'], 2)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
