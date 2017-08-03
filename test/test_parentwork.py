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
from beetsplug import parentwork


class FtInTitlePluginFunctional(unittest.TestCase, TestHelper):
    def setUp(self):
        """Set up configuration"""
        self.setup_beets()
        self.load_plugins('parentwork')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def _ft_add_item(self, path, artist, title, work_id):
        return self.add_item(path=path,
                             artist=artist,
                             title=title,
                             work_id=work_id,
                             parent_work=None,
                             parent_work_disambig=None,
                             parent_composer=None,
                             parent_composer_sort=None)

    def _ft_set_config(self, force):
        self.config['parentwork']['force'] = force

    def test_functional_drop(self):
        item = self._ft_add_item('/', u'Johann Sebastian Bach',
                                 u'Matthäus-Passion Part I Ouverture',
                                 u'2e4a3668-458d-3b2a-8be2-0b08e0d8243a')
        self.run_command('parentwork', '-f')
        item.load()
        self.assertEqual(item['parent_work'], u'Matthäus-Passion, BWV 244')
        self.assertEqual(item['parent_work_disambig'], u'')
        self.assertEqual(item['parent_composer'], u'Johann Sebastian Bach')
        self.assertEqual(item['parent_composer_sort'],
                         u'Bach, Johann Sebastian')
        self.assertEqual(item['parent_work_id'],
                         u'45afb3b2-18ac-4187-bc72-beb1b1c194ba')

    def test_functional_several_composers_disambig(self):
        item = self._ft_add_item('/', u'Mozart', u'Requiem I. Introitus',
                                 u'e27bda6e-531e-36d3-9cd7-b8ebc18e8c53')
        self.run_command('parentwork', '-f')
        item.load()
        self.assertEqual(item['parent_work'], u'Requiem in D minor, K. 626')
        self.assertEqual(item['parent_work_disambig'], u'Süßmayr Edition')
        self.assertEqual(item['parent_composer'],
                         u'Wolfgang Amadeus Mozart, Franz Xaver Süßmayr')
        self.assertEqual(item['parent_composer_sort'],
                         u'Mozart, Wolfgang Amadeus, Süßmayr, Franz Xaver')
        self.assertEqual(item['parent_work_id'],
                         u'32c8943f-1b27-3a23-8660-4567f4847c94')

    def test_functional_custom_format(self):
        self._ft_set_config('yes')
        item = self._ft_add_item('/', u'Mozart', u'Requiem I. Introitus',
                                 u'e27bda6e-531e-36d3-9cd7-b8ebc18e8c53')
        self.run_command('parentwork', '-f')
        item.load()
        self.assertEqual(item['parent_work'], u'Requiem in D minor, K. 626')
        self.assertEqual(item['parent_work_disambig'], u'Süßmayr Edition')
        self.assertEqual(item['parent_composer'],
                         u'Wolfgang Amadeus Mozart, Franz Xaver Süßmayr')
        self.assertEqual(item['parent_composer_sort'],
                         u'Mozart, Wolfgang Amadeus, Süßmayr, Franz Xaver')
        self.assertEqual(item['parent_work_id'],
                         u'32c8943f-1b27-3a23-8660-4567f4847c94')

        self._ft_set_config('no')
        item = self._ft_add_item(path='/', artist=u'Mozart',
                                 title=u'Requiem I. Introitus',
                                 work_id=u'e27bda6e-531e-36d3-\
                                 9cd7-b8ebc18e8c53',
                                 parent_work=u'Requiem in D minor, K. 626',
                                 parent_work_disambig=u'Süßmayr Edition',
                                 parent_composer=u'Wolfgang Amadeus Mozart, \
                                 Franz Xaver Süßmayr',
                                 parent_work_id=u'32c8943f-1b27-3a23-\
                                 8660-4567f4847c94')
        self.run_command('parentwork', '-f')
        item.load()
        # nothing should change
        self.assertEqual(item['parent_work'], u'Requiem in D minor, K. 626')
        self.assertEqual(item['parent_work_disambig'], u'Süßmayr Edition')
        self.assertEqual(item['parent_composer'],
                         u'Wolfgang Amadeus Mozart, Franz Xaver Süßmayr')
        self.assertEqual(item['parent_composer_sort'],
                         u'Mozart, Wolfgang Amadeus, Süßmayr, Franz Xaver')
        self.assertEqual(item['parent_work_id'],
                         u'32c8943f-1b27-3a23-8660-4567f4847c94')

    # test individual functions, still with Matthew Passion Ouverture

    def test_father_work(self):
        work_id = u'2e4a3668-458d-3b2a-8be2-0b08e0d8243a'
        self.assertEqual(u'f04b42df-7251-4d86-a5ee-67cfa49580d1',
                         parentwork.father_work(work_id))
        self.assertEqual(u'45afb3b2-18ac-4187-bc72-beb1b1c194ba',
                         parentwork.work_parent(work_id))


# class FtInTitlePluginTest(unittest.TestCase):
#    def setUp(self):
#        """Set up configuration"""
#        ftintitle.ParentWorkPlugin()
#
#    def test_find_feat_part(self):
#        test_cases = [
#            {
#                'artist': 'Alice ft. Bob',
#                'album_artist': 'Alice',
#                'feat_part': 'Bob'
#            },
#            {
#                'artist': 'Alice feat Bob',
#                'album_artist': 'Alice',
#                'feat_part': 'Bob'
#            },
#            {
#                'artist': 'Alice featuring Bob',
#                'album_artist': 'Alice',
#                'feat_part': 'Bob'
#            },
#            {
#                'artist': 'Alice & Bob',
#                'album_artist': 'Alice',
#                'feat_part': 'Bob'
#            },
#            {
#                'artist': 'Alice and Bob',
#                'album_artist': 'Alice',
#                'feat_part': 'Bob'
#            },
#            {
#                'artist': 'Alice With Bob',
#                'album_artist': 'Alice',
#                'feat_part': 'Bob'
#            },
#            {
#                'artist': 'Alice defeat Bob',
#                'album_artist': 'Alice',
#                'feat_part': None
#            },
#            {
#                'artist': 'Alice & Bob',
#                'album_artist': 'Bob',
#                'feat_part': 'Alice'
#            },
#            {
#                'artist': 'Alice ft. Bob',
#                'album_artist': 'Bob',
#                'feat_part': 'Alice'
#            },
#            {
#                'artist': 'Alice ft. Carol',
#                'album_artist': 'Bob',
#                'feat_part': None
#            },
#        ]
#
#        for test_case in test_cases:
#            feat_part = ftintitle.find_feat_part(
#                test_case['artist'],
#                test_case['album_artist']
#            )
#            self.assertEqual(feat_part, test_case['feat_part'])
#
#    def test_split_on_feat(self):
#        parts = ftintitle.split_on_feat(u'Alice ft. Bob')
#        self.assertEqual(parts, (u'Alice', u'Bob'))
#        parts = ftintitle.split_on_feat(u'Alice feat Bob')
#        self.assertEqual(parts, (u'Alice', u'Bob'))
#        parts = ftintitle.split_on_feat(u'Alice feat. Bob')
#        self.assertEqual(parts, (u'Alice', u'Bob'))
#        parts = ftintitle.split_on_feat(u'Alice featuring Bob')
#        self.assertEqual(parts, (u'Alice', u'Bob'))
#        parts = ftintitle.split_on_feat(u'Alice & Bob')
#        self.assertEqual(parts, (u'Alice', u'Bob'))
#        parts = ftintitle.split_on_feat(u'Alice and Bob')
#        self.assertEqual(parts, (u'Alice', u'Bob'))
#        parts = ftintitle.split_on_feat(u'Alice With Bob')
#        self.assertEqual(parts, (u'Alice', u'Bob'))
#        parts = ftintitle.split_on_feat(u'Alice defeat Bob')
#        self.assertEqual(parts, (u'Alice defeat Bob', None))
#
#    def test_contains_feat(self):
#        self.assertTrue(ftintitle.contains_feat(u'Alice ft. Bob'))
#        self.assertTrue(ftintitle.contains_feat(u'Alice feat. Bob'))
#        self.assertTrue(ftintitle.contains_feat(u'Alice feat Bob'))
#        self.assertTrue(ftintitle.contains_feat(u'Alice featuring Bob'))
#        self.assertTrue(ftintitle.contains_feat(u'Alice & Bob'))
#        self.assertTrue(ftintitle.contains_feat(u'Alice and Bob'))
#        self.assertTrue(ftintitle.contains_feat(u'Alice With Bob'))
#        self.assertFalse(ftintitle.contains_feat(u'Alice defeat Bob'))
#        self.assertFalse(ftintitle.contains_feat(u'Aliceft.Bob'))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
