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

"""Tests for the 'lastgenre' plugin."""

from _common import unittest
from beetsplug import lastgenre
from beets import config


class LastGenrePluginTest(unittest.TestCase):
    def setUp(self):
        """Set up configuration"""
        lastgenre.LastGenrePlugin()

    def _setup_config(self, _whitelist=set(), _branches=None, count=1):

        if _whitelist:
            lastgenre.options['whitelist'] = _whitelist
        if branches:
            lastgenre.options['branches'] = branches
            lastgenre.options['c14n'] = True
        else:
            lastgenre.options['c14n'] = False

        config['lastgenre']['count'] = count

    def test_c14n(self):
        """Resolve genres that belong to a canonicalization branch.
        """
        self._setup_config(whitelist=set(['blues']),
                           branches=[['blues'], ['blues', 'country blues'],
                                     ['blues', 'country blues',
                                      'delta blues']])

        self.assertEqual(lastgenre._strings_to_genre(['delta blues']), 'Blues')
        self.assertEqual(lastgenre._strings_to_genre(['rhytm n blues']), '')

    def test_whitelist(self):
        """Keep only genres that are in the whitelist.
        """
        self._setup_config(whitelist=set(['blues', 'rock', 'jazz']),
                           count=2)
        self.assertEqual(lastgenre._strings_to_genre(['pop', 'blues']),
                         'Blues')

    def test_count(self):
        """Keep the n first genres, as we expect them to be sorted from more to
        less popular.
        """
        self._setup_config(whitelist=set(['blues', 'rock', 'jazz']),
                           count=2)
        self.assertEqual(lastgenre._strings_to_genre(
                         ['jazz', 'pop', 'rock', 'blues']),
                         'Jazz, Rock')

    def test_count_c14n(self):
        """Keep the n first genres, after having applied c14n when necessary
        """
        self._setup_config(whitelist=set(['blues', 'rock', 'jazz']),
                           branches=[['blues'], ['blues', 'country blues']],
                           count=2)
        self.assertEqual(lastgenre._strings_to_genre(
                         ['jazz', 'pop', 'country blues', 'rock']),
                         'Jazz, Blues')

    def test_default_c14n(self):
        """c14n with default config files should work out-of-the-box
        """

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
