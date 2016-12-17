# -*- coding: utf-8 -*-

"""Tests for the 'zero' plugin"""

from __future__ import division, absolute_import, print_function

import unittest
from test.helper import TestHelper

from beets.library import Item
from beets import config
from beetsplug.zero import ZeroPlugin
from beets.mediafile import MediaFile
from beets.util import syspath


class ZeroPluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def test_no_patterns(self):
        tags = {
            'comments': u'test comment',
            'day': 13,
            'month': 3,
            'year': 2012,
        }
        z = ZeroPlugin()
        z.debug = False
        z.fields = ['comments', 'month', 'day']
        z.patterns = {'comments': [u'.'],
                      'month': [u'.'],
                      'day': [u'.']}
        z.write_event(None, None, tags)
        self.assertEqual(tags['comments'], None)
        self.assertEqual(tags['day'], None)
        self.assertEqual(tags['month'], None)
        self.assertEqual(tags['year'], 2012)

    def test_patterns(self):
        z = ZeroPlugin()
        z.debug = False
        z.fields = ['comments', 'year']
        z.patterns = {'comments': u'eac lame'.split(),
                      'year': u'2098 2099'.split()}

        tags = {
            'comments': u'from lame collection, ripped by eac',
            'year': 2012,
        }
        z.write_event(None, None, tags)
        self.assertEqual(tags['comments'], None)
        self.assertEqual(tags['year'], 2012)

    def test_delete_replaygain_tag(self):
        path = self.create_mediafile_fixture()
        item = Item.from_path(path)
        item.rg_track_peak = 0.0
        item.write()

        mediafile = MediaFile(syspath(item.path))
        self.assertIsNotNone(mediafile.rg_track_peak)
        self.assertIsNotNone(mediafile.rg_track_gain)

        config['zero'] = {
            'fields': ['rg_track_peak', 'rg_track_gain'],
        }
        self.load_plugins('zero')

        item.write()
        mediafile = MediaFile(syspath(item.path))
        self.assertIsNone(mediafile.rg_track_peak)
        self.assertIsNone(mediafile.rg_track_gain)

    def test_do_not_change_database(self):
        item = self.add_item_fixture(year=2000)
        item.write()
        mediafile = MediaFile(syspath(item.path))
        self.assertEqual(2000, mediafile.year)

        config['zero'] = {'fields': ['year']}
        self.load_plugins('zero')

        item.write()
        mediafile = MediaFile(syspath(item.path))
        self.assertEqual(item['year'], 2000)
        self.assertIsNone(mediafile.year)

    def test_change_database(self):
        item = self.add_item_fixture(year=2000)
        item.write()
        mediafile = MediaFile(syspath(item.path))
        self.assertEqual(2000, mediafile.year)

        config['zero'] = {
            'fields': [u'year'],
            'update_database': True,
        }
        self.load_plugins('zero')

        item.write()
        mediafile = MediaFile(syspath(item.path))
        self.assertEqual(item['year'], 0)
        self.assertIsNone(mediafile.year)

    def test_album_art(self):
        path = self.create_mediafile_fixture(images=['jpg'])
        item = Item.from_path(path)

        mediafile = MediaFile(syspath(item.path))
        self.assertNotEqual(0, len(mediafile.images))

        config['zero'] = {'fields': [u'images']}
        self.load_plugins('zero')

        item.write()
        mediafile = MediaFile(syspath(item.path))
        self.assertEqual(0, len(mediafile.images))

    def test_auto_false(self):
        item = self.add_item_fixture(year=2000)
        item.write()
        mediafile = MediaFile(syspath(item.path))
        self.assertEqual(2000, mediafile.year)

        config['zero'] = {
            'fields': [u'year'],
            'update_database': True,
            'auto': False
        }
        self.load_plugins('zero')

        item.write()
        mediafile = MediaFile(syspath(item.path))
        self.assertEqual(item['year'], 2000)
        self.assertEqual(mediafile.year, 2000)

    def test_subcommand_update_database_true(self):
        item = self.add_item_fixture(
            year=2016,
            day=13,
            month=3,
            comments=u'test comment'
        )
        item.write()
        item_id = item.id
        config['zero'] = {
            'fields': [u'comments'],
            'update_database': True,
            'auto': False
        }
        self.load_plugins('zero')
        self.run_command('zero')

        mediafile = MediaFile(syspath(item.path))
        item = self.lib.get_item(item_id)

        self.assertEqual(item['year'], 2016)
        self.assertEqual(mediafile.year, 2016)
        self.assertEqual(mediafile.comments, None)
        self.assertEqual(item['comments'], u'')

    def test_subcommand_update_database_false(self):
        item = self.add_item_fixture(
            year=2016,
            day=13,
            month=3,
            comments=u'test comment'
        )
        item.write()
        item_id = item.id
        config['zero'] = {
            'fields': [u'comments'],
            'update_database': False,
            'auto': False
        }
        self.load_plugins('zero')
        self.run_command('zero')

        mediafile = MediaFile(syspath(item.path))
        item = self.lib.get_item(item_id)

        self.assertEqual(item['year'], 2016)
        self.assertEqual(mediafile.year, 2016)
        self.assertEqual(item['comments'], u'test comment')
        self.assertEqual(mediafile.comments, None)

    def test_subcommand_query_include(self):
        item = self.add_item_fixture(
            year=2016,
            day=13,
            month=3,
            comments=u'test comment'
        )

        item.write()

        config['zero'] = {
            'fields': [u'comments'],
            'update_database': False,
            'auto': False
        }

        self.load_plugins('zero')
        self.run_command('zero', 'year: 2016')

        mediafile = MediaFile(syspath(item.path))

        self.assertEqual(mediafile.year, 2016)
        self.assertEqual(mediafile.comments, None)

    def test_subcommand_query_exclude(self):
        item = self.add_item_fixture(
            year=2016,
            day=13,
            month=3,
            comments=u'test comment'
        )

        item.write()

        config['zero'] = {
            'fields': [u'comments'],
            'update_database': False,
            'auto': False
        }

        self.load_plugins('zero')
        self.run_command('zero', 'year: 0000')

        mediafile = MediaFile(syspath(item.path))

        self.assertEqual(mediafile.year, 2016)
        self.assertEqual(mediafile.comments, u'test comment')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
