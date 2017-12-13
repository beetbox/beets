# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2017, Dorian Soergel
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

"""Tests for the 'parentwork' plugin."""

from __future__ import division, absolute_import, print_function

import unittest
from test.helper import TestHelper
from beetsplug import parentwork


class ParentWorkPluginFunctional(unittest.TestCase, TestHelper):
    def setUp(self):
        """Set up configuration"""
        self.setup_beets()
        self.load_plugins('parentwork')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def _pw_add_item(self, artist, title, work_id, parent_work=None,
                     parent_work_disambig=None, parent_composer=None,
                     parent_work_id=None):
        return self.add_item(artist=artist,
                             title=title,
                             work_id=work_id,
                             parent_work=parent_work,
                             parent_work_disambig=parent_work_disambig,
                             parent_composer=parent_composer,
                             parent_composer_sort=parent_work_id)

    def _pw_set_config(self, force):
        self.config['parentwork']['force'] = force

    def test_normal_case(self):
        item = self._pw_add_item(artist=u'Johann Sebastian Bach',
                                 title=u'Matthäus-Passion Part I Ouverture',
                                 work_id=u'2e4a3668-458d-\
                                 3b2a-8be2-0b08e0d8243a')
        self.run_command('parentwork', '-f')
        item.load()
        self.assertEqual(item['parent_work'], u'Matthäus-Passion, BWV 244')
        self.assertEqual(item['parent_work_disambig'], u'')
        self.assertEqual(item['parent_composer'], u'Johann Sebastian Bach')
        self.assertEqual(item['parent_composer_sort'],
                         u'Bach, Johann Sebastian')
        self.assertEqual(item['parent_work_id'],
                         u'45afb3b2-18ac-4187-bc72-beb1b1c194ba')

    def test_several_composers_disambig(self):
        item = self._pw_add_item(artist=u'Mozart',
                                 title=u'Requiem I. Introitus',
                                 work_id=u'e27bda6e-531e-\
                                 36d3-9cd7-b8ebc18e8c53')
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

    def test_force_in_config(self):
        self._pw_set_config('yes')
        item = self._pw_add_item(artist=u'Mozart',
                                 title=u'Requiem I. Introitus',
                                 work_id=u'e27bda6e-531e-36d3-\
                                 9cd7-b8ebc18e8c53')
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

        self._pw_set_config('no')
        item = self._pw_add_item(artist=u'Mozart',
                                 title=u'Requiem II. Kyrie',
                                 work_id=u'6eaede01-c31a-3402\
                                 -bedb-598e6bcbad03',
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
                         parentwork.work_father(work_id))
        self.assertEqual(u'45afb3b2-18ac-4187-bc72-beb1b1c194ba',
                         parentwork.work_parent(work_id))


class ParentworkPluginTest(unittest.TestCase):
    def setUp(self):
        """Set up configuration"""
        parentwork.ParentWorkPlugin()

    def test_find_feat_part(self):
        test_cases = [
            {
                'work_id': u'6eaede01-c31a-3402\
                                 -bedb-598e6bcbad03',
                'father_work_id': '32c8943f-1b27-3a23-8660-4567f4847c94',
                'parent_work': u'Requiem in D minor, K. 626',
                'parent_work_disambig': u'Süßmayr Edition',
                'parent_composer': u'Wolfgang Amadeus Mozart, \
                                 Franz Xaver Süßmayr',
                'parent_work_id': u'32c8943f-1b27-3a23-\
                                 8660-4567f4847c94',
                'parent_composer_sort': u'Mozart, Wolfgang Amadeus, \
                                Süßmayr, Franz Xaver',
                'parent_work_disambig': u'Süßmayr Edition'
            },
            {
                'work_id': u'2e4a3668-458d-3b2a-8be2-0b08e0d8243a',
                'father_work_id': 'f04b42df-7251-4d86-a5ee-67cfa49580d1',
                'parent_work': u'Matthäus-Passion, BWV 244',
                'parent_work_disambig': u'',
                'parent_composer': u'Johann Sebastian Bach',
                'parent_composer_sort': u'Bach, Johann Sebastian',
                'parent_work_id': u'45afb3b2-18ac-4187-bc72-beb1b1c194ba'
            },
        ]

        for test_case in test_cases:
            feat_part = parentwork.work_father(
                test_case[0]['work_id'],
                force=True
            )
            self.assertEqual(feat_part, test_case[0]['father_work_id'])
            feat_part = parentwork.work_parent(
                test_case[1]['work_id'],
                force=True
            )
            self.assertEqual(feat_part, test_case[1]['parent_work_id'])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
