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

import os
import unittest
from test.helper import TestHelper

from beets.library import Item
from beetsplug import parentwork
import musicbrainzngs

work = {'work': {'id': '1',
                 'work-relation-list': [{'type': 'parts',
                                         'direction': 'backwards',
                                         'id': '2'}],
                 'artist-relation-list': [{'type': 'composer',
                                           'artist': {'name':
                                                      'random composer',
                                                      'sort-name':
                                                      'composer, random'}}]}}
dp_work = {'work': {'id': '2',
                    'work-relation-list': [{'type': 'parts',
                                            'direction': 'backwards',
                                            'id': '3'}],
                    'artist-relation-list': [{'type': 'composer',
                                              'artist': {'name':
                                                         'random composer',
                                                         'sort-name':
                                                         'composer, random'
                                                         }}]}}
p_work = {'work': {'id': '3',
                   'artist-relation-list': [{'type': 'composer',
                                             'artist': {'name':
                                                        'random composer',
                                                        'sort-name':
                                                        'composer, random'}}]}}


def mock_workid_response(mbid):
    if mbid == '1':
        return work
    elif mbid == '2':
        return dp_work
    elif mbid == '3':
        return p_work


class ParentWorkTest(unittest.TestCase, TestHelper):
    def setUp(self):
        """Set up configuration"""
        self.setup_beets()
        self.load_plugins('parentwork')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    @unittest.mock.patch('musicbrainzngs.get_work_by_id',
                         side_effect=mock_workid_response)
    @unittest.skipUnless(
        os.environ.get('INTEGRATION_TEST', '0') == '1',
        'integration testing not enabled')
    def test_normal_case(self):
        item = Item(path='/file',
                    mb_workid='1')
        item.add(self.lib)

        self.run_command('parentwork')

        item.load()
        self.assertEqual(item['mb_parentworkid'],
                         '3')

    @unittest.skipUnless(
        os.environ.get('INTEGRATION_TEST', '0') == '1',
        'integration testing not enabled')
    def test_force(self):
        self.config['parentwork']['force'] = True
        item = Item(path='/file',
                    mb_workid='1',
                    mb_parentworkid=u'XXX')
        item.add(self.lib)

        self.run_command('parentwork')

        item.load()
        self.assertEqual(item['mb_parentworkid'],
                         '3')

    @unittest.skipUnless(
        os.environ.get('INTEGRATION_TEST', '0') == '1',
        'integration testing not enabled')
    def test_no_force(self):
        self.config['parentwork']['force'] = True
        item = Item(path='/file', mb_workid='1', mb_parentworkid=u'XXX')
        item.add(self.lib)

        self.run_command('parentwork')

        item.load()
        self.assertEqual(item['mb_parentworkid'], '3')

    # test different cases, still with Matthew Passion Ouverture or Mozart
    # requiem

    @unittest.skipUnless(
        os.environ.get('INTEGRATION_TEST', '0') == '1',
        'integration testing not enabled')
    def test_direct_parent_work(self):
        self.assertEqual('2',
                         parentwork.direct_parent_id('1')[0])
        self.assertEqual('3',
                         parentwork.work_parent_id('1')[0])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
