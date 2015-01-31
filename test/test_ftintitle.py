# This file is part of beets.
# Copyright 2015, Fabrice Laporte.
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

"""Tests for the 'ftintitle' plugin."""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from test._common import unittest
from beetsplug import ftintitle


class FtInTitlePluginTest(unittest.TestCase):
    def setUp(self):
        """Set up configuration"""
        ftintitle.FtInTitlePlugin()

    def test_find_feat_part(self):
        test_cases = [
            {
                'artist': 'Alice ft. Bob',
                'album_artist': 'Alice',
                'feat_part': 'Bob'
            },
            {
                'artist': 'Alice feat Bob',
                'album_artist': 'Alice',
                'feat_part': 'Bob'
            },
            {
                'artist': 'Alice featuring Bob',
                'album_artist': 'Alice',
                'feat_part': 'Bob'
            },
            {
                'artist': 'Alice & Bob',
                'album_artist': 'Alice',
                'feat_part': 'Bob'
            },
            {
                'artist': 'Alice and Bob',
                'album_artist': 'Alice',
                'feat_part': 'Bob'
            },
            {
                'artist': 'Alice With Bob',
                'album_artist': 'Alice',
                'feat_part': 'Bob'
            },
            {
                'artist': 'Alice defeat Bob',
                'album_artist': 'Alice',
                'feat_part': None
            },
            {
                'artist': 'Alice & Bob',
                'album_artist': 'Bob',
                'feat_part': 'Alice'
            },
            {
                'artist': 'Alice ft. Bob',
                'album_artist': 'Bob',
                'feat_part': 'Alice'
            },
        ]

        for test_case in test_cases:
            feat_part = ftintitle.find_feat_part(
                test_case['artist'],
                test_case['album_artist']
            )
            self.assertEqual(feat_part, test_case['feat_part'])

    def test_split_on_feat(self):
        parts = ftintitle.split_on_feat('Alice ft. Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice feat Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice feat. Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice featuring Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice & Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice and Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice With Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice defeat Bob')
        self.assertEqual(parts, ('Alice defeat Bob', None))

    def test_contains_feat(self):
        self.assertTrue(ftintitle.contains_feat('Alice ft. Bob'))
        self.assertTrue(ftintitle.contains_feat('Alice feat. Bob'))
        self.assertTrue(ftintitle.contains_feat('Alice feat Bob'))
        self.assertTrue(ftintitle.contains_feat('Alice featuring Bob'))
        self.assertTrue(ftintitle.contains_feat('Alice & Bob'))
        self.assertTrue(ftintitle.contains_feat('Alice and Bob'))
        self.assertTrue(ftintitle.contains_feat('Alice With Bob'))
        self.assertFalse(ftintitle.contains_feat('Alice defeat Bob'))
        self.assertFalse(ftintitle.contains_feat('Aliceft.Bob'))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
