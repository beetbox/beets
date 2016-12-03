# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Fabrice Laporte.
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

from __future__ import division, absolute_import, print_function

import unittest
from test.helper import TestHelper
from beetsplug import ftintitle


class FtInTitlePluginFunctional(unittest.TestCase, TestHelper):
    def setUp(self):
        """Set up configuration"""
        self.setup_beets()
        self.load_plugins('ftintitle')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def _ft_add_item(self, path, artist, title, aartist):
        return self.add_item(path=path,
                             artist=artist,
                             artist_sort=artist,
                             title=title,
                             albumartist=aartist)

    def _ft_set_config(self, ftformat, drop=False, auto=True):
        self.config['ftintitle']['format'] = ftformat
        self.config['ftintitle']['drop'] = drop
        self.config['ftintitle']['auto'] = auto

    def test_functional_drop(self):
        item = self._ft_add_item('/', u'Alice ft Bob', u'Song 1', u'Alice')
        self.run_command('ftintitle', '-d')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1')

    def test_functional_not_found(self):
        item = self._ft_add_item('/', u'Alice ft Bob', u'Song 1', u'George')
        self.run_command('ftintitle', '-d')
        item.load()
        # item should be unchanged
        self.assertEqual(item['artist'], u'Alice ft Bob')
        self.assertEqual(item['title'], u'Song 1')

    def test_functional_custom_format(self):
        self._ft_set_config('feat. {0}')
        item = self._ft_add_item('/', u'Alice ft Bob', u'Song 1', u'Alice')
        self.run_command('ftintitle')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1 feat. Bob')

        self._ft_set_config('featuring {0}')
        item = self._ft_add_item('/', u'Alice feat. Bob', u'Song 1', u'Alice')
        self.run_command('ftintitle')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1 featuring Bob')

        self._ft_set_config('with {0}')
        item = self._ft_add_item('/', u'Alice feat Bob', u'Song 1', u'Alice')
        self.run_command('ftintitle')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1 with Bob')


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
            {
                'artist': 'Alice ft. Carol',
                'album_artist': 'Bob',
                'feat_part': None
            },
        ]

        for test_case in test_cases:
            feat_part = ftintitle.find_feat_part(
                test_case['artist'],
                test_case['album_artist']
            )
            self.assertEqual(feat_part, test_case['feat_part'])

    def test_split_on_feat(self):
        parts = ftintitle.split_on_feat(u'Alice ft. Bob')
        self.assertEqual(parts, (u'Alice', u'Bob'))
        parts = ftintitle.split_on_feat(u'Alice feat Bob')
        self.assertEqual(parts, (u'Alice', u'Bob'))
        parts = ftintitle.split_on_feat(u'Alice feat. Bob')
        self.assertEqual(parts, (u'Alice', u'Bob'))
        parts = ftintitle.split_on_feat(u'Alice featuring Bob')
        self.assertEqual(parts, (u'Alice', u'Bob'))
        parts = ftintitle.split_on_feat(u'Alice & Bob')
        self.assertEqual(parts, (u'Alice', u'Bob'))
        parts = ftintitle.split_on_feat(u'Alice and Bob')
        self.assertEqual(parts, (u'Alice', u'Bob'))
        parts = ftintitle.split_on_feat(u'Alice With Bob')
        self.assertEqual(parts, (u'Alice', u'Bob'))
        parts = ftintitle.split_on_feat(u'Alice defeat Bob')
        self.assertEqual(parts, (u'Alice defeat Bob', None))

    def test_contains_feat(self):
        self.assertTrue(ftintitle.contains_feat(u'Alice ft. Bob'))
        self.assertTrue(ftintitle.contains_feat(u'Alice feat. Bob'))
        self.assertTrue(ftintitle.contains_feat(u'Alice feat Bob'))
        self.assertTrue(ftintitle.contains_feat(u'Alice featuring Bob'))
        self.assertTrue(ftintitle.contains_feat(u'Alice & Bob'))
        self.assertTrue(ftintitle.contains_feat(u'Alice and Bob'))
        self.assertTrue(ftintitle.contains_feat(u'Alice With Bob'))
        self.assertFalse(ftintitle.contains_feat(u'Alice defeat Bob'))
        self.assertFalse(ftintitle.contains_feat(u'Aliceft.Bob'))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
