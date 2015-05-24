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

"""Tests for the 'lastgenre' plugin."""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from mock import Mock

from test import _common
from test._common import unittest
from beetsplug import lastgenre
from beets import config

from test.helper import TestHelper


class LastGenrePluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.plugin = lastgenre.LastGenrePlugin()

    def tearDown(self):
        self.teardown_beets()

    def _setup_config(self, whitelist=False, canonical=False, count=1):
        config['lastgenre']['canonical'] = canonical
        config['lastgenre']['count'] = count
        if isinstance(whitelist, (bool, basestring)):
            # Filename, default, or disabled.
            config['lastgenre']['whitelist'] = whitelist
        self.plugin.setup()
        if not isinstance(whitelist, (bool, basestring)):
            # Explicit list of genres.
            self.plugin.whitelist = whitelist

    def test_default(self):
        """Fetch genres with whitelist and c14n deactivated
        """
        self._setup_config()
        self.assertEqual(self.plugin._resolve_genres(['delta blues']),
                         'Delta Blues')

    def test_c14n_only(self):
        """Default c14n tree funnels up to most common genre except for *wrong*
        genres that stay unchanged.
        """
        self._setup_config(canonical=True, count=99)
        self.assertEqual(self.plugin._resolve_genres(['delta blues']),
                         'Blues')
        self.assertEqual(self.plugin._resolve_genres(['iota blues']),
                         'Iota Blues')

    def test_whitelist_only(self):
        """Default whitelist rejects *wrong* (non existing) genres.
        """
        self._setup_config(whitelist=True)
        self.assertEqual(self.plugin._resolve_genres(['iota blues']),
                         '')

    def test_whitelist_c14n(self):
        """Default whitelist and c14n both activated result in all parents
        genres being selected (from specific to common).
        """
        self._setup_config(canonical=True, whitelist=True, count=99)
        self.assertEqual(self.plugin._resolve_genres(['delta blues']),
                         'Delta Blues, Blues')

    def test_whitelist_custom(self):
        """Keep only genres that are in the whitelist.
        """
        self._setup_config(whitelist=set(['blues', 'rock', 'jazz']),
                           count=2)
        self.assertEqual(self.plugin._resolve_genres(['pop', 'blues']),
                         'Blues')

        self._setup_config(canonical='', whitelist=set(['rock']))
        self.assertEqual(self.plugin._resolve_genres(['delta blues']),
                         '')

    def test_count(self):
        """Keep the n first genres, as we expect them to be sorted from more to
        less popular.
        """
        self._setup_config(whitelist=set(['blues', 'rock', 'jazz']),
                           count=2)
        self.assertEqual(self.plugin._resolve_genres(
                         ['jazz', 'pop', 'rock', 'blues']),
                         'Jazz, Rock')

    def test_count_c14n(self):
        """Keep the n first genres, after having applied c14n when necessary
        """
        self._setup_config(whitelist=set(['blues', 'rock', 'jazz']),
                           canonical=True,
                           count=2)
        # thanks to c14n, 'blues' superseeds 'country blues' and takes the
        # second slot
        self.assertEqual(self.plugin._resolve_genres(
                         ['jazz', 'pop', 'country blues', 'rock']),
                         'Jazz, Blues')

    def test_c14n_whitelist(self):
        """Genres first pass through c14n and are then filtered
        """
        self._setup_config(canonical=True, whitelist=set(['rock']))
        self.assertEqual(self.plugin._resolve_genres(['delta blues']),
                         '')

    def test_empty_string_enables_canonical(self):
        """For backwards compatibility, setting the `canonical` option
        to the empty string enables it using the default tree.
        """
        self._setup_config(canonical='', count=99)
        self.assertEqual(self.plugin._resolve_genres(['delta blues']),
                         'Blues')

    def test_empty_string_enables_whitelist(self):
        """Again for backwards compatibility, setting the `whitelist`
        option to the empty string enables the default set of genres.
        """
        self._setup_config(whitelist='')
        self.assertEqual(self.plugin._resolve_genres(['iota blues']),
                         '')

    def test_no_duplicate(self):
        """Remove duplicated genres.
        """
        self._setup_config(count=99)
        self.assertEqual(self.plugin._resolve_genres(['blues', 'blues']),
                         'Blues')

    def test_tags_for(self):
        class MockPylastElem(object):
            def __init__(self, name):
                self.name = name

            def get_name(self):
                return self.name

        class MockPylastObj(object):
            def get_top_tags(self):
                tag1 = Mock()
                tag1.weight = 90
                tag1.item = MockPylastElem(u'Pop')
                tag2 = Mock()
                tag2.weight = 40
                tag2.item = MockPylastElem(u'Rap')
                return [tag1, tag2]

        plugin = lastgenre.LastGenrePlugin()
        res = plugin._tags_for(MockPylastObj())
        self.assertEqual(res, [u'pop', u'rap'])
        res = plugin._tags_for(MockPylastObj(), min_weight=50)
        self.assertEqual(res, [u'pop'])

    def test_get_genre(self):
        MOCK_GENRES = {'track': u'1', 'album': u'2', 'artist': u'3'}

        def mock_fetch_track_genre(self, obj=None):
            return MOCK_GENRES['track']

        def mock_fetch_album_genre(self, obj):
            return MOCK_GENRES['album']

        def mock_fetch_artist_genre(self, obj):
            return MOCK_GENRES['artist']

        lastgenre.LastGenrePlugin.fetch_track_genre = mock_fetch_track_genre
        lastgenre.LastGenrePlugin.fetch_album_genre = mock_fetch_album_genre
        lastgenre.LastGenrePlugin.fetch_artist_genre = mock_fetch_artist_genre

        self._setup_config(whitelist=False)
        item = _common.item()
        item.genre = MOCK_GENRES['track']

        config['lastgenre'] = {'force': False}
        res = self.plugin._get_genre(item)
        self.assertEqual(res, (item.genre, 'keep'))

        config['lastgenre'] = {'force': True, 'source': 'track'}
        res = self.plugin._get_genre(item)
        self.assertEqual(res, (MOCK_GENRES['track'], 'track'))

        config['lastgenre'] = {'source': 'album'}
        res = self.plugin._get_genre(item)
        self.assertEqual(res, (MOCK_GENRES['album'], 'album'))

        config['lastgenre'] = {'source': 'artist'}
        res = self.plugin._get_genre(item)
        self.assertEqual(res, (MOCK_GENRES['artist'], 'artist'))

        MOCK_GENRES['artist'] = None
        res = self.plugin._get_genre(item)
        self.assertEqual(res, (item.genre, 'original'))

        config['lastgenre'] = {'fallback': 'rap'}
        item.genre = None
        res = self.plugin._get_genre(item)
        self.assertEqual(res, (config['lastgenre']['fallback'].get(),
                         'fallback'))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
