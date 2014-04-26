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

import logging
import os
from _common import unittest
from beetsplug import lastgenre
from beets import config

log = logging.getLogger('beets')

lastGenrePlugin = lastgenre.LastGenrePlugin()


class LastGenrePluginTest(unittest.TestCase):

    def _setup_config(self, whitelist=set(), canonical=None, count=1):
        config['lastgenre']['canonical'] = canonical
        config['lastgenre']['count'] = count
        config['lastgenre']['whitelist'] = \
            os.path.join(os.path.dirname(lastgenre.__file__), 'genres.txt')
        lastGenrePlugin.setup()
        if whitelist:
            lastGenrePlugin.whitelist = whitelist

    def test_c14n(self):
        """Resolve genres that belong to a canonicalization branch.
        """
        # default whitelist and c14n
        self._setup_config(canonical=' ')
        self.assertEqual(lastGenrePlugin._resolve_genres(['delta blues']),
                         'Blues')
        self.assertEqual(lastGenrePlugin._resolve_genres(['iota blues']), '')

        # custom whitelist
        self._setup_config(canonical='', whitelist=set(['rock']))
        self.assertEqual(lastGenrePlugin._resolve_genres(['delta blues']),
                         '')

    def test_whitelist(self):
        """Keep only genres that are in the whitelist.
        """
        self._setup_config(whitelist=set(['blues', 'rock', 'jazz']),
                           count=2)
        self.assertEqual(lastGenrePlugin._resolve_genres(['pop', 'blues']),
                         'Blues')

    def test_count(self):
        """Keep the n first genres, as we expect them to be sorted from more to
        less popular.
        """
        self._setup_config(whitelist=set(['blues', 'rock', 'jazz']),
                           count=2)
        self.assertEqual(lastGenrePlugin._resolve_genres(
                         ['jazz', 'pop', 'rock', 'blues']),
                         'Jazz, Rock')

    def test_count_c14n(self):
        """Keep the n first genres, after having applied c14n when necessary
        """
        self._setup_config(whitelist=set(['blues', 'rock', 'jazz']),
                           canonical='',
                           count=2)

        # thanks to c14n, 'blues' superseeds 'country blues' and takes the
        # second slot
        self.assertEqual(lastGenrePlugin._resolve_genres(
                         ['jazz', 'pop', 'country blues', 'rock']),
                         'Jazz, Blues')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
