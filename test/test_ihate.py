"""Tests for the 'ihate' plugin"""


import unittest
from beets import importer
from beets.library import Item
from beetsplug.ihate import IHatePlugin, summary
from test import helper


class IHatePluginTest(unittest.TestCase, helper.TestHelper):

    def test_hate(self):

        match_pattern = {}
        test_item = Item(
            genre='TestGenre',
            album='TestAlbum',
            artist='TestArtist')
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

    def test_summary(self):
        # Task is not album
        test_item = Item(
            artist='TestArtist',
            title='TestTitle')
        task = importer.SingletonImportTask(None, test_item)
        self.assertEqual(
            summary(task),
            'TestArtist - TestTitle'
        )

    def test_import_task(self):
        # Task choice is skip
        match_pattern = {}
        test_item = Item(
            genre='TestGenre',
            album='TestAlbum',
            artist='TestArtist')
        test_task = importer.SingletonImportTask(None, test_item)
        match_pattern = ["album:testalbum genre:testgenre",
                         "artist:testartist album:notthis"]
        test_task.choice_flag = importer.action.APPLY
        test_plugin = IHatePlugin()
        test_plugin.config['skip'] = match_pattern
        test_plugin.import_task_choice_event(test_plugin, test_task)
        self.assertEqual(
            test_task.choice_flag,
            importer.action.SKIP
        )


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
