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

"""Basic tests for the objects that are used to represent the beets
library and the items in it.
"""

import unittest
import sys
sys.path.append('..')
from beets.library import BaseLibrary, BaseAlbum

class AlbumTest(unittest.TestCase):

    def test_field_access(self):
        album = BaseAlbum(None, {'artist':'foo', 'albumartist':'bar'})
        self.assertEqual(album.artist, 'foo')
        self.assertEqual(album.albumartist, 'bar')

    def test_field_access_unset_values(self):
        """
        This is how things work currently. Trying to access unset album
        metadata raises an AttributeError.
        """
        album = BaseAlbum(None, {})
        self.assertRaises(AttributeError, getattr, album, 'albumartist')
        self.assertRaises(AttributeError, getattr, album, 'artist')

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')

