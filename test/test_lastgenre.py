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
from _common import unittest
from beetsplug import lastgenre
from beets import config

log = logging.getLogger('beets')

lastGenrePlugin = lastgenre.LastGenrePlugin()


class LastGenrePluginTest(unittest.TestCase):

    def _setup_config(self, whitelist='false', canonical='false', count=1):
        config['lastgenre']['canonical'] = canonical
        config['lastgenre']['count'] = count
        if whitelist in ('true', 'false'):
            config['lastgenre']['whitelist'] = whitelist
        lastGenrePlugin.setup()
        if whitelist not in ('true', 'false'):
            lastGenrePlugin.whitelist = whitelist

    def test_default(self):
        """Fetch genres with whitelist and c14n deactivated
        """
        self._setup_config()
        self.assertEqual(lastGenrePlugin._resolve_genres(['delta blues']),
                         'Delta Blues')

    def test_c14n_only(self):
        """Default c14n tree funnels up to most common genre except for *wrong*
        genres that stay unchanged.
        """
        self._setup_config(canonical='true', count=99)
        self.assertEqual(lastGenrePlugin._resolve_genres(['delta blues']),
                         'Blues')
        self.assertEqual(lastGenrePlugin._resolve_genres(['iota blues']),
                         'Iota Blues')

    def test_whitelist_only(self):
        """Default whitelist rejects *wrong* (non existing) genres.
        """
        self._setup_config(whitelist='true')
        self.assertEqual(lastGenrePlugin._resolve_genres(['iota blues']),
                         '')

    def test_whitelist_c14n(self):
        """Default whitelist and c14n both activated result in all parents
        genres being selected (from specific to common).
        """
        self._setup_config(canonical='true', whitelist='true', count=99)
        self.assertEqual(lastGenrePlugin._resolve_genres(['delta blues']),
                         'Delta Blues, Country Blues, Blues')

    def test_whitelist_custom(self):
        """Keep only genres that are in the whitelist.
        """
        self._setup_config(whitelist=set(['blues', 'rock', 'jazz']),
                           count=2)
        self.assertEqual(lastGenrePlugin._resolve_genres(['pop', 'blues']),
                         'Blues')

        self._setup_config(canonical='', whitelist=set(['rock']))
        self.assertEqual(lastGenrePlugin._resolve_genres(['delta blues']),
                         '')

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
                           canonical='true',
                           count=2)
        # thanks to c14n, 'blues' superseeds 'country blues' and takes the
        # second slot
        self.assertEqual(lastGenrePlugin._resolve_genres(
                         ['jazz', 'pop', 'country blues', 'rock']),
                         'Jazz, Blues')

    def test_c14n_whitelist(self):
        """Genres first pass through c14n and are then filtered
        """
        self._setup_config(canonical='true', whitelist=set(['rock']))
        self.assertEqual(lastGenrePlugin._resolve_genres(['delta blues']),
                         '')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
