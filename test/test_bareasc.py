# -*- coding: utf-8 -*-

"""Tests for the 'bareasc' plugin"""

from __future__ import division, absolute_import, print_function

import unittest

from test.helper import TestHelper

from beets import logging


class BareascPluginTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()
        self.log = logging.getLogger('beets.web')
        self.config['bareasc']['prefix'] = u'#'
        self.load_plugins('bareasc')

        # Add library elements. Note that self.lib.add overrides any "id=<n>"
        # and assigns the next free id number.
        self.add_item(title=u'with accents',
                      album_id=2,
                      artist=u'dvořák')
        self.add_item(title=u'without accents',
                      artist=u'dvorak')
        self.add_item(title=u'with umlaut',
                      album_id=2,
                      artist=u'Brüggen')
        self.add_item(title=u'without umlaut',
                      artist=u'Bruggen')

    def test_search_normal_noaccent(self):
        items = self.lib.items('dvorak')

        self.assertEqual(len(items), 1)
        self.assertEqual([items[0].title], [u'without accents'])

    def test_search_normal_accent(self):
        items = self.lib.items('dvořák')

        self.assertEqual(len(items), 1)
        self.assertEqual([items[0].title], [u'with accents'])

    def test_search_bareasc_noaccent(self):
        items = self.lib.items('#dvorak')

        self.assertEqual(len(items), 2)
        self.assertEqual(
            {items[0].title, items[1].title},
            {u'without accents', u'with accents'}
        )

    def test_search_bareasc_accent(self):
        items = self.lib.items('#dvořák')

        self.assertEqual(len(items), 2)
        self.assertEqual(
            {items[0].title, items[1].title},
            {u'without accents', u'with accents'}
        )

    def test_search_bareasc_noumlaut(self):
        items = self.lib.items('#Bruggen')

        self.assertEqual(len(items), 2)
        self.assertEqual(
            {items[0].title, items[1].title},
            {u'without umlaut', u'with umlaut'}
        )

    def test_search_bareasc_umlaut(self):
        items = self.lib.items('#Brüggen')

        self.assertEqual(len(items), 2)
        self.assertEqual(
            {items[0].title, items[1].title},
            {u'without umlaut', u'with umlaut'}
        )


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
