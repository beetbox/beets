# -*- coding: utf-8 -*-

"""Tests for the 'zero' plugin"""

from __future__ import division, absolute_import, print_function

import unittest
from test.helper import TestHelper, control_stdin

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

        mf = MediaFile(syspath(path))
        self.assertEqual(0, len(mf.images))

    def test_auto_false(self):
        self.config['zero']['fields'] = ['year']
        self.config['zero']['update_database'] = True
        self.config['zero']['auto'] = False

        item = self.add_item_fixture(year=2000)
        item.write()

        self.load_plugins('zero')
        item.write()

        self.assertEqual(item['year'], 2000)

    def test_subcommand_update_database_true(self):
        item = self.add_item_fixture(
            year=2016,
            day=13,
            month=3,
            comments=u'test comment'
        )
        item.write()
        item_id = item.id
        self.config['zero']['fields'] = ['comments']
        self.config['zero']['update_database'] = True
        self.config['zero']['auto'] = False

        self.load_plugins('zero')
        with control_stdin('y'):
            self.run_command('zero')

        mf = MediaFile(syspath(item.path))
        item = self.lib.get_item(item_id)

        self.assertEqual(item['year'], 2016)
        self.assertEqual(mf.year, 2016)
        self.assertEqual(mf.comments, None)
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

        self.config['zero']['fields'] = ['comments']
        self.config['zero']['update_database'] = False
        self.config['zero']['auto'] = False

        self.load_plugins('zero')
        with control_stdin('y'):
            self.run_command('zero')

        mf = MediaFile(syspath(item.path))
        item = self.lib.get_item(item_id)

        self.assertEqual(item['year'], 2016)
        self.assertEqual(mf.year, 2016)
        self.assertEqual(item['comments'], u'test comment')
        self.assertEqual(mf.comments, None)

    def test_subcommand_query_include(self):
        item = self.add_item_fixture(
            year=2016,
            day=13,
            month=3,
            comments=u'test comment'
        )

        item.write()

        self.config['zero']['fields'] = ['comments']
        self.config['zero']['update_database'] = False
        self.config['zero']['auto'] = False

        self.load_plugins('zero')
        self.run_command('zero', 'year: 2016')

        mf = MediaFile(syspath(item.path))

        self.assertEqual(mf.year, 2016)
        self.assertEqual(mf.comments, None)

    def test_subcommand_query_exclude(self):
        item = self.add_item_fixture(
            year=2016,
            day=13,
            month=3,
            comments=u'test comment'
        )

        item.write()

        self.config['zero']['fields'] = ['comments']
        self.config['zero']['update_database'] = False
        self.config['zero']['auto'] = False

        self.load_plugins('zero')
        self.run_command('zero', 'year: 0000')

        mf = MediaFile(syspath(item.path))

        self.assertEqual(mf.year, 2016)
        self.assertEqual(mf.comments, u'test comment')

    def test_no_fields(self):
        item = self.add_item_fixture(year=2016)
        item.write()
        mediafile = MediaFile(syspath(item.path))
        self.assertEqual(mediafile.year, 2016)

        item_id = item.id

        self.load_plugins('zero')
        with control_stdin('y'):
            self.run_command('zero')

        item = self.lib.get_item(item_id)

        self.assertEqual(item['year'], 2016)
        self.assertEqual(mediafile.year, 2016)

    def test_whitelist_and_blacklist(self):
        item = self.add_item_fixture(year=2016)
        item.write()
        mf = MediaFile(syspath(item.path))
        self.assertEqual(mf.year, 2016)

        item_id = item.id
        self.config['zero']['fields'] = [u'year']
        self.config['zero']['keep_fields'] = [u'comments']

        self.load_plugins('zero')
        with control_stdin('y'):
            self.run_command('zero')

        item = self.lib.get_item(item_id)

        self.assertEqual(item['year'], 2016)
        self.assertEqual(mf.year, 2016)

    def test_keep_fields(self):
        item = self.add_item_fixture(year=2016, comments=u'test comment')
        self.config['zero']['keep_fields'] = [u'year']
        self.config['zero']['fields'] = None
        self.config['zero']['update_database'] = True

        tags = {
            'comments': u'test comment',
            'year': 2016,
        }
        self.load_plugins('zero')

        z = ZeroPlugin()
        z.write_event(item, item.path, tags)
        self.assertEqual(tags['comments'], None)
        self.assertEqual(tags['year'], 2016)

    def test_keep_fields_removes_preserved_tags(self):
        self.config['zero']['keep_fields'] = [u'year']
        self.config['zero']['fields'] = None
        self.config['zero']['update_database'] = True

        z = ZeroPlugin()

        self.assertNotIn('id', z.fields_to_progs)

    def test_fields_removes_preserved_tags(self):
        self.config['zero']['fields'] = [u'year id']
        self.config['zero']['update_database'] = True

        z = ZeroPlugin()

        self.assertNotIn('id', z.fields_to_progs)

    def test_empty_query_n_response_no_changes(self):
        item = self.add_item_fixture(
            year=2016,
            day=13,
            month=3,
            comments=u'test comment'
        )
        item.write()
        item_id = item.id
        self.config['zero']['fields'] = ['comments']
        self.config['zero']['update_database'] = True
        self.config['zero']['auto'] = False

        self.load_plugins('zero')
        with control_stdin('n'):
            self.run_command('zero')

        mf = MediaFile(syspath(item.path))
        item = self.lib.get_item(item_id)

        self.assertEqual(item['year'], 2016)
        self.assertEqual(mf.year, 2016)
        self.assertEqual(mf.comments, u'test comment')
        self.assertEqual(item['comments'], u'test comment')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
