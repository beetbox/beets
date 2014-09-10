# This file is part of beets.
# Copyright 2014, Fabrice Laporte.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Tests for the 'lyrics' plugin."""

from _common import unittest
from beetsplug import lyrics
from beets.library import Item


class LyricsPluginTest(unittest.TestCase):
    def setUp(self):
        """Set up configuration"""
        lyrics.LyricsPlugin()

    def test_search_artist(self):
        item = Item(artist='Alice ft. Bob', title='song')
        self.assertIn(('Alice ft. Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertIn(('Alice', ['song']),
                      lyrics.search_pairs(item))

        item = Item(artist='Alice feat Bob', title='song')
        self.assertIn(('Alice feat Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertIn(('Alice', ['song']),
                      lyrics.search_pairs(item))

        item = Item(artist='Alice feat. Bob', title='song')
        self.assertIn(('Alice feat. Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertIn(('Alice', ['song']),
                      lyrics.search_pairs(item))

        item = Item(artist='Alice feats Bob', title='song')
        self.assertIn(('Alice feats Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertNotIn(('Alice', ['song']),
                         lyrics.search_pairs(item))

        item = Item(artist='Alice featuring Bob', title='song')
        self.assertIn(('Alice featuring Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertIn(('Alice', ['song']),
                      lyrics.search_pairs(item))

        item = Item(artist='Alice & Bob', title='song')
        self.assertIn(('Alice & Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertIn(('Alice', ['song']),
                      lyrics.search_pairs(item))

        item = Item(artist='Alice and Bob', title='song')
        self.assertIn(('Alice and Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertIn(('Alice', ['song']),
                      lyrics.search_pairs(item))

    def test_search_pairs_multi_titles(self):
        item = Item(title='1 / 2', artist='A')
        self.assertIn(('A', ['1 / 2']), lyrics.search_pairs(item))
        self.assertIn(('A', ['1', '2']), lyrics.search_pairs(item))

        item = Item(title='1/2', artist='A')
        self.assertIn(('A', ['1/2']), lyrics.search_pairs(item))
        self.assertIn(('A', ['1', '2']), lyrics.search_pairs(item))

    def test_search_pairs_titles(self):
        item = Item(title='Song (live)', artist='A')
        self.assertIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song (live)']), lyrics.search_pairs(item))

        item = Item(title='Song (live) (new)', artist='A')
        self.assertIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song (live) (new)']), lyrics.search_pairs(item))

        item = Item(title='Song (live (new))', artist='A')
        self.assertIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song (live (new))']), lyrics.search_pairs(item))

        item = Item(title='Song ft. B', artist='A')
        self.assertIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song ft. B']), lyrics.search_pairs(item))

        item = Item(title='Song featuring B', artist='A')
        self.assertIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song featuring B']), lyrics.search_pairs(item))

        item = Item(title='Song and B', artist='A')
        self.assertNotIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song and B']), lyrics.search_pairs(item))

    def test_remove_credits(self):
        self.assertEqual(
            lyrics.remove_credits("""It's close to midnight
                                     Lyrics brought by example.com"""),
            "It's close to midnight"
        )
        self.assertEqual(
            lyrics.remove_credits("""Lyrics brought by example.com"""),
            ""
        )
        text = """Look at all the shit that i done bought her
                  See lyrics ain't nothin
                  if the beat aint crackin"""
        self.assertEqual(lyrics.remove_credits(text), text)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
