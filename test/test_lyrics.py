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
        self.assertEqual(
            lyrics.remove_ft_artist_suffix('Bob featuring Marcia'),
            'Bob'
        )
        self.assertEqual(
            lyrics.remove_ft_artist_suffix('Bob feat Marcia'),
            'Bob'
        )
        self.assertEqual(
            lyrics.remove_ft_artist_suffix('Bob and Marcia'),
            'Bob'
        )
        self.assertEqual(
            lyrics.remove_ft_artist_suffix('Bob feat. Marcia'),
            'Bob'
        )
        self.assertEqual(
            lyrics.remove_ft_artist_suffix('Bob & Marcia'),
            'Bob'
        )
        self.assertEqual(
            lyrics.remove_ft_artist_suffix('Bob feats Marcia'),
            'Bob feats Marcia'
        )

    def test_remove_parenthesized_suffix(self):
        self.assertEqual(
            lyrics.remove_parenthesized_suffix('Song (live)'),
            'Song'
        )
        self.assertEqual(
            lyrics.remove_parenthesized_suffix('Song (live) (new)'),
            'Song'
        )
        self.assertEqual(
            lyrics.remove_parenthesized_suffix('Song (live (new))'),
            'Song'
        )

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
