# -*- coding: utf-8 -*-

"""Tests for the 'zero' plugin"""

from __future__ import division, absolute_import, print_function

import unittest
from test.helper import TestHelper

from beets.library import Item
from beetsplug.zero import ZeroPlugin
from beets.mediafile import MediaFile
from beets.util import syspath


class ZeroPluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.config['zero'] = {
            'fields': [],
            'keep_fields': [],
            'update_database': False,
        }

    def tearDown(self):
        ZeroPlugin.listeners = None
        self.teardown_beets()
        self.unload_plugins()

    def test_no_patterns(self):
        self.config['zero']['fields'] = ['comments', 'month']

        item = self.add_item_fixture(
            comments=u'test comment',
            title=u'Title',
            month=1,
            year=2000,
        )
        item.write()

        self.load_plugins('zero')
        item.write()

        mf = MediaFile(syspath(item.path))
        self.assertIsNone(mf.comments)
        self.assertIsNone(mf.month)
        self.assertEqual(mf.title, u'Title')
        self.assertEqual(mf.year, 2000)

    def test_pattern_match(self):
        self.config['zero']['fields'] = ['comments']
        self.config['zero']['comments'] = [u'encoded by']

        item = self.add_item_fixture(comments=u'encoded by encoder')
        item.write()

        self.load_plugins('zero')
        item.write()

        mf = MediaFile(syspath(item.path))
        self.assertIsNone(mf.comments)

    def test_pattern_nomatch(self):
        self.config['zero']['fields'] = ['comments']
        self.config['zero']['comments'] = [u'encoded by']

        item = self.add_item_fixture(comments=u'recorded at place')
        item.write()

        self.load_plugins('zero')
        item.write()

        mf = MediaFile(syspath(item.path))
        self.assertEqual(mf.comments, u'recorded at place')

    def test_do_not_change_database(self):
        self.config['zero']['fields'] = ['year']

        item = self.add_item_fixture(year=2000)
        item.write()

        self.load_plugins('zero')
        item.write()

        self.assertEqual(item['year'], 2000)

    def test_change_database(self):
        self.config['zero']['fields'] = ['year']
        self.config['zero']['update_database'] = True

        item = self.add_item_fixture(year=2000)
        item.write()

        self.load_plugins('zero')
        item.write()

        self.assertEqual(item['year'], 0)

    def test_album_art(self):
        self.config['zero']['fields'] = ['images']

        path = self.create_mediafile_fixture(images=['jpg'])
        item = Item.from_path(path)

        self.load_plugins('zero')
        item.write()

        mediafile = MediaFile(syspath(path))
        self.assertEqual(0, len(mediafile.images))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
