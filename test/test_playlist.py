# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Thomas Scholtes.
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

from __future__ import division, absolute_import, print_function
from six.moves import shlex_quote

import os
import shutil
import tempfile
import unittest

from test import _common
from test import helper

import beets


class PlaylistTest(unittest.TestCase, helper.TestHelper):
    def setUp(self):
        self.setup_beets()
        self.lib = beets.library.Library(':memory:')

        self.music_dir = os.path.expanduser('~/Music')

        i1 = _common.item()
        i1.path = beets.util.normpath(os.path.join(
            self.music_dir,
            'a', 'b', 'c.mp3',
        ))
        i1.title = u'some item'
        i1.album = u'some album'
        self.lib.add(i1)
        self.lib.add_album([i1])

        i2 = _common.item()
        i2.path = beets.util.normpath(os.path.join(
            self.music_dir,
            'd', 'e', 'f.mp3',
        ))
        i2.title = 'another item'
        i2.album = 'another album'
        self.lib.add(i2)
        self.lib.add_album([i2])

        i3 = _common.item()
        i3.path = beets.util.normpath(os.path.join(
            self.music_dir,
            'x', 'y', 'z.mp3',
        ))
        i3.title = 'yet another item'
        i3.album = 'yet another album'
        self.lib.add(i3)
        self.lib.add_album([i3])

        self.playlist_dir = tempfile.mkdtemp()
        with open(os.path.join(self.playlist_dir, 'test.m3u'), 'w') as f:
            f.write('{0}\n'.format(beets.util.displayable_path(i1.path)))
            f.write('{0}\n'.format(beets.util.displayable_path(i2.path)))

        self.config['directory'] = self.music_dir
        self.config['playlist']['relative_to'] = 'library'
        self.config['playlist']['playlist_dir'] = self.playlist_dir
        self.load_plugins('playlist')

    def tearDown(self):
        self.unload_plugins()
        shutil.rmtree(self.playlist_dir)
        self.teardown_beets()

    def test_query_name(self):
        q = u'playlist:test'
        results = self.lib.items(q)
        self.assertEqual(set([i.title for i in results]), set([
            u'some item',
            u'another item',
        ]))

    def test_query_path(self):
        q = u'playlist:{0}'.format(shlex_quote(os.path.join(
            self.playlist_dir,
            'test.m3u',
        )))
        results = self.lib.items(q)
        self.assertEqual(set([i.title for i in results]), set([
            u'some item',
            u'another item',
        ]))

    def test_query_name_nonexisting(self):
        q = u'playlist:nonexisting'.format(self.playlist_dir)
        results = self.lib.items(q)
        self.assertEqual(set(results), set())

    def test_query_path_nonexisting(self):
        q = u'playlist:{0}'.format(shlex_quote(os.path.join(
            self.playlist_dir,
            self.playlist_dir,
            'nonexisting.m3u',
        )))
        results = self.lib.items(q)
        self.assertEqual(set(results), set())


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
