"""Tests for the 'zero' plugin"""

from _common import unittest
from helper import TestHelper

from beets.library import Item
from beetsplug.zero import ZeroPlugin
from beets.mediafile import MediaFile


class ZeroPluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.zero = self.config['zero']

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def test_remove_item_fields(self):
        i = Item(
            comments='test comment',
            day=13,
            month=3,
            year=2012,
        )
        self.zero['fields'] = ['comments', 'month', 'day']
        ZeroPlugin().write_event(i)
        self.assertIsNone(i.comments)
        self.assertIsNone(i.day)
        self.assertIsNone(i.month)
        self.assertEqual(i.year, 2012)

    def test_remove_fields_on_patterns(self):
        i = Item(
            comments='from lame collection, ripped by eac',
            year=2012,
        )
        self.zero['fields'] = ['comments', 'day']
        self.zero['patterns'] = {
            'comments': 'eac lame'.split(),
            'year': '2098 2099'.split()
        }

        ZeroPlugin().write_event(i)
        self.assertIsNone(i.comments)
        self.assertEqual(i.year, 2012)

    def test_delete_replaygain_tag(self):
        path = self.create_mediafile_fixture()
        item = Item.from_path(path)
        item.rg_track_peak = 0.0
        item.write()

        mediafile = MediaFile(item.path)
        self.assertIsNotNone(mediafile.rg_track_peak)
        self.assertIsNotNone(mediafile.rg_track_gain)

        self.zero['fields'] = ['rg_track_peak', 'rg_track_gain']
        self.load_plugins('zero')

        item.write()
        mediafile = MediaFile(item.path)
        self.assertIsNone(mediafile.rg_track_peak)
        self.assertIsNone(mediafile.rg_track_gain)

    def test_delete_composer_and_comments_tag(self):
        path = self.create_mediafile_fixture('mp3')
        item = Item.from_path(path)
        item.composer = 'somebody'
        item.comments = 'comment'
        item.write()
        # We user mutagen to make sure that the tag is (non)existent.
        self.assertIn("TCOM", MediaFile(item.path).mgfile)
        self.assertIn("COMM::'eng'", MediaFile(item.path).mgfile)

        self.zero['fields'] = ['composer', 'comments']
        self.load_plugins('zero')

        item.write()
        self.assertNotIn("TCOM", MediaFile(item.path).mgfile)
        self.assertNotIn("COMM::'eng'", MediaFile(item.path).mgfile)

    def test_delete_track_tags(self):
        path = self.create_mediafile_fixture('mp3')
        item = Item.from_path(path)
        self.assertIn('TRCK', MediaFile(item.path).mgfile)

        self.zero['fields'] = ['track', 'tracktotal']
        self.load_plugins('zero')

        item.write()
        self.assertNotIn('TRCK', MediaFile(item.path).mgfile)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
