# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

"""Tests for the albumify upgrader plugin."""

import unittest
import sys

sys.path.append('..')
from beets import library
from beets import ui
from beetsplug.albumify import albumify

from test_db import item

# Silence UI output.
ui.print_ = lambda s: None

class AlbumifyTest(unittest.TestCase):
    def setUp(self):
        self.lib = library.Library(':memory:')
        i1, i2, i3 = item(), item(), item()
        i1.album = 'album1'
        i2.album = 'album1'
        i3.album = 'album2'
        self.lib.add(i1)
        self.lib.add(i2)
        self.lib.add(i3)

    def test_albumify_creates_albums(self):
        albumify(self.lib)
        albums = [a.album for a in self.lib.albums()]
        self.assert_('album1' in albums)
        self.assert_('album2' in albums)

    def test_albumify_groups_items(self):
        albumify(self.lib)
        q = library.MatchQuery('album', 'album1')
        album1 = self.lib.albums(query=q)[0]
        self.assertEqual(len( list(album1.items()) ), 2)
        q = library.MatchQuery('album', 'album2')
        album2 = self.lib.albums(query=q)[0]
        self.assertEqual(len( list(album2.items()) ), 1)

    def test_albumify_does_not_duplicate_existing_albums(self):
        i4 = item()
        i4.album = 'album3'
        self.lib.add_album([i4])
        self.assertEqual(len( list(self.lib.albums()) ), 1)
        albumify(self.lib)
        self.assertEqual(len( list(self.lib.albums()) ), 3)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
