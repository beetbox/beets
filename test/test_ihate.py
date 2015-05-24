"""Tests for the 'ihate' plugin"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from test._common import unittest
from beets import importer
from beets.library import Item
from beetsplug.ihate import IHatePlugin


class IHatePluginTest(unittest.TestCase):

    def test_hate(self):

        match_pattern = {}
        test_item = Item(
            genre='TestGenre',
            album=u'TestAlbum',
            artist=u'TestArtist')
        task = importer.SingletonImportTask(None, test_item)

        # Empty query should let it pass.
        self.assertFalse(IHatePlugin.do_i_hate_this(task, match_pattern))

        # 1 query match.
        match_pattern = ["artist:bad_artist", "artist:TestArtist"]
        self.assertTrue(IHatePlugin.do_i_hate_this(task, match_pattern))

        # 2 query matches, either should trigger.
        match_pattern = ["album:test", "artist:testartist"]
        self.assertTrue(IHatePlugin.do_i_hate_this(task, match_pattern))

        # Query is blocked by AND clause.
        match_pattern = ["album:notthis genre:testgenre"]
        self.assertFalse(IHatePlugin.do_i_hate_this(task, match_pattern))

        # Both queries are blocked by AND clause with unmatched condition.
        match_pattern = ["album:notthis genre:testgenre",
                         "artist:testartist album:notthis"]
        self.assertFalse(IHatePlugin.do_i_hate_this(task, match_pattern))

        # Only one query should fire.
        match_pattern = ["album:testalbum genre:testgenre",
                         "artist:testartist album:notthis"]
        self.assertTrue(IHatePlugin.do_i_hate_this(task, match_pattern))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
