# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2021, Graham R. Cobb.

"""Tests for the 'bareasc' plugin."""

from __future__ import division, absolute_import, print_function

import unittest

from test.helper import capture_stdout, TestHelper

from beets import logging


class BareascPluginTest(unittest.TestCase, TestHelper):
    """Test bare ASCII query matching."""

    def setUp(self):
        """Set up test environment for bare ASCII query matching."""
        self.setup_beets()
        self.log = logging.getLogger('beets.web')
        self.config['bareasc']['prefix'] = u'#'
        self.load_plugins('bareasc')

        # Add library elements. Note that self.lib.add overrides any "id=<n>"
        # and assigns the next free id number.
        self.add_item(title=u'with accents',
                      album_id=2,
                      artist=u'Antonín Dvořák')
        self.add_item(title=u'without accents',
                      artist=u'Antonín Dvorak')
        self.add_item(title=u'with umlaut',
                      album_id=2,
                      artist=u'Brüggen')
        self.add_item(title=u'without umlaut or e',
                      artist=u'Bruggen')
        self.add_item(title=u'without umlaut with e',
                      artist=u'Brueggen')

    def test_search_normal_noaccent(self):
        """Normal search, no accents, not using bare-ASCII match.

        Finds just the unaccented entry.
        """
        items = self.lib.items(u'dvorak')

        self.assertEqual(len(items), 1)
        self.assertEqual([items[0].title], [u'without accents'])

    def test_search_normal_accent(self):
        """Normal search, with accents, not using bare-ASCII match.

        Finds just the accented entry.
        """
        items = self.lib.items(u'dvořák')

        self.assertEqual(len(items), 1)
        self.assertEqual([items[0].title], [u'with accents'])

    def test_search_bareasc_noaccent(self):
        """Bare-ASCII search, no accents.

        Finds both entries.
        """
        items = self.lib.items(u'#dvorak')

        self.assertEqual(len(items), 2)
        self.assertEqual(
            {items[0].title, items[1].title},
            {u'without accents', u'with accents'}
        )

    def test_search_bareasc_accent(self):
        """Bare-ASCII search, with accents.

        Finds both entries.
        """
        items = self.lib.items(u'#dvořák')

        self.assertEqual(len(items), 2)
        self.assertEqual(
            {items[0].title, items[1].title},
            {u'without accents', u'with accents'}
        )

    def test_search_bareasc_wrong_accent(self):
        """Bare-ASCII search, with incorrect accent.

        Finds both entries.
        """
        items = self.lib.items(u'#dvořäk')

        self.assertEqual(len(items), 2)
        self.assertEqual(
            {items[0].title, items[1].title},
            {u'without accents', u'with accents'}
        )

    def test_search_bareasc_noumlaut(self):
        """Bare-ASCII search, with no umlaut.

        Finds entry with 'u' not 'ue', although German speaker would
        normally replace ü with ue.

        This is expected behaviour for this simple plugin.
        """
        items = self.lib.items(u'#Bruggen')

        self.assertEqual(len(items), 2)
        self.assertEqual(
            {items[0].title, items[1].title},
            {u'without umlaut or e', u'with umlaut'}
        )

    def test_search_bareasc_umlaut(self):
        """Bare-ASCII search, with umlaut.

        Finds entry with 'u' not 'ue', although German speaker would
        normally replace ü with ue.

        This is expected behaviour for this simple plugin.
        """
        items = self.lib.items(u'#Brüggen')

        self.assertEqual(len(items), 2)
        self.assertEqual(
            {items[0].title, items[1].title},
            {u'without umlaut or e', u'with umlaut'}
        )

    def test_bareasc_list_output(self):
        """Bare-ASCII version of list command - check output."""
        with capture_stdout() as output:
            self.run_command('bareasc', 'with accents')

        self.assertIn('Antonin Dvorak', output.getvalue())

    def test_bareasc_format_output(self):
        """Bare-ASCII version of list -f command - check output."""
        with capture_stdout() as output:
            self.run_command('bareasc', 'with accents',
                             '-f', '$artist:: $title')

        self.assertEqual('Antonin Dvorak:: with accents\n',
                         output.getvalue())


def suite():
    """loader."""
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
