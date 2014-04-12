#!/usr/bin/python
# -*- coding: UTF-8 -*-

"""Tests for the 'lyrics' plugin"""

import _common
from _common import unittest
from beetsplug import lyrics
from beets import config
from beets.util import confit


class LyricsPluginTest(unittest.TestCase):
    def setUp(self):
        """Set up configuration"""
        lyrics.LyricsPlugin()

    def test_split_multi_titles(self):
        self.assertEqual(lyrics.split_multi_titles('song1 / song2 / song3'),
                         ['song1', 'song2', 'song3'])
        self.assertEqual(lyrics.split_multi_titles('song1/song2 song3'),
                         ['song1', 'song2 song3'])
        self.assertEqual(lyrics.split_multi_titles('song1 song2'),
                         None)

    def test_remove_ft_artist_suffix(self):
        self.assertEqual(lyrics.remove_ft_artist_suffix('Bob featuring Marcia'), 'Bob')
        self.assertEqual(lyrics.remove_ft_artist_suffix('Bob feat Marcia'), 'Bob')
        self.assertEqual(lyrics.remove_ft_artist_suffix('Bob and Marcia'), 'Bob')
        self.assertEqual(lyrics.remove_ft_artist_suffix('Bob feat. Marcia'), 'Bob')
        self.assertEqual(lyrics.remove_ft_artist_suffix('Bob & Marcia'), 'Bob')
        self.assertEqual(lyrics.remove_ft_artist_suffix('Bob feats Marcia'), 'Bob feats Marcia')

    def test_remove_parenthesized_suffix(self):
        self.assertEqual(lyrics.remove_parenthesized_suffix('Song (live)'), 'Song')
        self.assertEqual(lyrics.remove_parenthesized_suffix('Song (live) (new)'), 'Song')
        self.assertEqual(lyrics.remove_parenthesized_suffix('Song (live (new))'), 'Song')

        
def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')

