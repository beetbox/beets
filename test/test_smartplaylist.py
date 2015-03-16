# This file is part of beets.
# Copyright 2015, Bruno Cauet.
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

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from os import path
from tempfile import mkdtemp
from shutil import rmtree

from mock import Mock, MagicMock

from beetsplug.smartplaylist import SmartPlaylistPlugin
from beets.library import Item, Album, parse_query_string
from beets.dbcore import OrQuery
from beets.util import syspath
from beets import config

from test._common import unittest
from test.helper import TestHelper


class SmartPlaylistTest(unittest.TestCase):
    def test_build_queries(self):
        spl = SmartPlaylistPlugin()
        self.assertEqual(spl._matched_playlists, None)
        self.assertEqual(spl._unmatched_playlists, None)

        config['smartplaylist']['playlists'].set([])
        spl.build_queries()
        self.assertEqual(spl._matched_playlists, set())
        self.assertEqual(spl._unmatched_playlists, set())

        config['smartplaylist']['playlists'].set([
            {'name': 'foo',
             'query': 'FOO foo'},
            {'name': 'bar',
             'album_query': ['BAR bar1', 'BAR bar2']},
            {'name': 'baz',
             'query': 'BAZ baz',
             'album_query': 'BAZ baz'}
        ])
        spl.build_queries()
        self.assertEqual(spl._matched_playlists, set())
        foo_foo, _ = parse_query_string('FOO foo', Item)
        bar_bar = OrQuery([parse_query_string('BAR bar1', Album)[0],
                           parse_query_string('BAR bar2', Album)[0]])
        baz_baz, _ = parse_query_string('BAZ baz', Item)
        baz_baz2, _ = parse_query_string('BAZ baz', Album)
        self.assertEqual(spl._unmatched_playlists, {
            ('foo', foo_foo, None),
            ('bar', None, bar_bar),
            ('baz', baz_baz, baz_baz2)
        })

    def test_db_changes(self):
        spl = SmartPlaylistPlugin()

        i1 = MagicMock(Item)
        i2 = MagicMock(Item)
        a = MagicMock(Album)
        i1.get_album.return_value = a

        q1 = Mock()
        q1.matches.side_effect = {i1: False, i2: False}.__getitem__
        a_q1 = Mock()
        a_q1.matches.side_effect = {a: True}.__getitem__
        q2 = Mock()
        q2.matches.side_effect = {i1: False, i2: True}.__getitem__

        pl1 = ('1', q1, a_q1)
        pl2 = ('2', None, a_q1)
        pl3 = ('3', q2, None)

        spl._unmatched_playlists = {pl1, pl2, pl3}
        spl._matched_playlists = set()
        spl.db_change(None, i1)
        self.assertEqual(spl._unmatched_playlists, {pl2})
        self.assertEqual(spl._matched_playlists, {pl1, pl3})

        spl._unmatched_playlists = {pl1, pl2, pl3}
        spl._matched_playlists = set()
        spl.db_change(None, i2)
        self.assertEqual(spl._unmatched_playlists, {pl2})
        self.assertEqual(spl._matched_playlists, {pl1, pl3})

        spl._unmatched_playlists = {pl1, pl2, pl3}
        spl._matched_playlists = set()
        spl.db_change(None, a)
        self.assertEqual(spl._unmatched_playlists, {pl3})
        self.assertEqual(spl._matched_playlists, {pl1, pl2})
        spl.db_change(None, i2)
        self.assertEqual(spl._unmatched_playlists, set())
        self.assertEqual(spl._matched_playlists, {pl1, pl2, pl3})

    def test_playlist_update(self):
        spl = SmartPlaylistPlugin()

        i = Mock(path='/tagada.mp3')
        i.evaluate_template.side_effect = lambda x, _: x
        q = Mock()
        a_q = Mock()
        lib = Mock()
        lib.items.return_value = [i]
        lib.albums.return_value = []
        pl = 'my_playlist.m3u', q, a_q
        spl._matched_playlists = {pl}

        dir = mkdtemp()
        config['smartplaylist']['relative_to'] = False
        config['smartplaylist']['playlist_dir'] = dir
        try:
            spl.update_playlists(lib)
        except Exception:
            rmtree(dir)
            raise

        lib.items.assert_called_once_with(q)
        lib.albums.assert_called_once_with(a_q)

        m3u_filepath = path.join(dir, pl[0])
        self.assertTrue(path.exists(m3u_filepath), m3u_filepath)

        with open(syspath(m3u_filepath), 'r') as f:
            content = f.readlines()
        rmtree(dir)

        self.assertEqual(content, ["/tagada.mp3\n"])


class SmartPlaylistCLITest(unittest.TestCase, TestHelper):
    def test_import(self):
        pass

    def test_splupdate(self):
        pass
