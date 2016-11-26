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

"""Tests for the 'lastgenre' plugin."""

from __future__ import division, absolute_import, print_function

import unittest
from mock import Mock

from test import _common
from beetsplug import lastgenre
from beets import config

from test.helper import TestHelper
import six


class LastGenrePluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.plugin = lastgenre.LastGenrePlugin()

    def tearDown(self):
        self.teardown_beets()

    def _setup_config(self, whitelist=False, canonical=False, count=1):
        config['lastgenre']['canonical'] = canonical
        config['lastgenre']['count'] = count
        if isinstance(whitelist, (bool, six.string_types)):
            # Filename, default, or disabled.
            config['lastgenre']['whitelist'] = whitelist
        self.plugin.setup()
        if not isinstance(whitelist, (bool, six.string_types)):
            # Explicit list of genres.
            self.plugin.whitelist = whitelist

    def test_default(self):
        """Fetch genres with whitelist and c14n deactivated
        """
        self._setup_config()
        self.assertEqual(self.plugin._resolve_genres(['delta blues']),
                         u'Delta Blues')

    def test_c14n_only(self):
        """Default c14n tree funnels up to most common genre except for *wrong*
        genres that stay unchanged.
        """
        self._setup_config(canonical=True, count=99)
        self.assertEqual(self.plugin._resolve_genres(['delta blues']),
                         u'Blues')
        self.assertEqual(self.plugin._resolve_genres(['iota blues']),
                         u'Iota Blues')

    def test_whitelist_only(self):
        """Default whitelist rejects *wrong* (non existing) genres.
        """
        self._setup_config(whitelist=True)
        self.assertEqual(self.plugin._resolve_genres(['iota blues']),
                         u'')

    def test_whitelist_c14n(self):
        """Default whitelist and c14n both activated result in all parents
        genres being selected (from specific to common).
        """
        self._setup_config(canonical=True, whitelist=True, count=99)
        self.assertEqual(self.plugin._resolve_genres(['delta blues']),
                         u'Delta Blues, Blues')

    def test_whitelist_custom(self):
        """Keep only genres that are in the whitelist.
        """
        self._setup_config(whitelist=set(['blues', 'rock', 'jazz']),
                           count=2)
        self.assertEqual(self.plugin._resolve_genres(['pop', 'blues']),
                         u'Blues')

        self._setup_config(canonical='', whitelist=set(['rock']))
        self.assertEqual(self.plugin._resolve_genres(['delta blues']),
                         u'')

    def test_count(self):
        """Keep the n first genres, as we expect them to be sorted from more to
        less popular.
        """
        self._setup_config(whitelist=set(['blues', 'rock', 'jazz']),
                           count=2)
        self.assertEqual(self.plugin._resolve_genres(
                         ['jazz', 'pop', 'rock', 'blues']),
                         u'Jazz, Rock')

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
                         u'Jazz, Blues')

    def test_c14n_whitelist(self):
        """Genres first pass through c14n and are then filtered
        """
        self._setup_config(canonical=True, whitelist=set(['rock']))
        self.assertEqual(self.plugin._resolve_genres(['delta blues']),
                         u'')

    def test_empty_string_enables_canonical(self):
        """For backwards compatibility, setting the `canonical` option
        to the empty string enables it using the default tree.
        """
        self._setup_config(canonical='', count=99)
        self.assertEqual(self.plugin._resolve_genres(['delta blues']),
                         u'Blues')

    def test_empty_string_enables_whitelist(self):
        """Again for backwards compatibility, setting the `whitelist`
        option to the empty string enables the default set of genres.
        """
        self._setup_config(whitelist='')
        self.assertEqual(self.plugin._resolve_genres(['iota blues']),
                         u'')

    def test_no_duplicate(self):
        """Remove duplicated genres.
        """
        self._setup_config(count=99)
        self.assertEqual(self.plugin._resolve_genres(['blues', 'blues']),
                         u'Blues')

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
        mock_genres = {'track': u'1', 'album': u'2', 'artist': u'3'}

        def mock_fetch_track_genre(self, obj=None):
            return mock_genres['track']

        def mock_fetch_album_genre(self, obj):
            return mock_genres['album']

        def mock_fetch_artist_genre(self, obj):
            return mock_genres['artist']

        lastgenre.LastGenrePlugin.fetch_track_genre = mock_fetch_track_genre
        lastgenre.LastGenrePlugin.fetch_album_genre = mock_fetch_album_genre
        lastgenre.LastGenrePlugin.fetch_artist_genre = mock_fetch_artist_genre

        self._setup_config(whitelist=False)
        item = _common.item()
        item.genre = mock_genres['track']

        config['lastgenre'] = {'force': False}
        res = self.plugin._get_genre(item)
        self.assertEqual(res, (item.genre, u'keep'))

        config['lastgenre'] = {'force': True, 'source': u'track'}
        res = self.plugin._get_genre(item)
        self.assertEqual(res, (mock_genres['track'], u'track'))

        config['lastgenre'] = {'source': u'album'}
        res = self.plugin._get_genre(item)
        self.assertEqual(res, (mock_genres['album'], u'album'))

        config['lastgenre'] = {'source': u'artist'}
        res = self.plugin._get_genre(item)
        self.assertEqual(res, (mock_genres['artist'], u'artist'))

        mock_genres['artist'] = None
        res = self.plugin._get_genre(item)
        self.assertEqual(res, (item.genre, u'original'))

        config['lastgenre'] = {'fallback': u'rap'}
        item.genre = None
        res = self.plugin._get_genre(item)
        self.assertEqual(res, (config['lastgenre']['fallback'].get(),
                         u'fallback'))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
