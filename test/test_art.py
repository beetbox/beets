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

"""Tests for the album art fetchers."""

import unittest
import sys

sys.path.insert(0, '..')
from beets.autotag import art

class MockHeaders(object):
    def __init__(self, typeval):
        self.typeval = typeval
    def gettype(self):
        return self.typeval
class MockUrlRetrieve(object):
    def __init__(self, pathval, typeval):
        self.pathval = pathval
        self.headers = MockHeaders(typeval)
    def __call__(self, url):
        return self.pathval, self.headers

class AmazonArtTest(unittest.TestCase):
    def test_invalid_type_returns_none(self):
        art.urllib.urlretrieve = MockUrlRetrieve('path', '')
        artpath = art.art_for_asin('xxxx')
        self.assertEqual(artpath, None)

    def test_jpeg_type_returns_path(self):
        art.urllib.urlretrieve = MockUrlRetrieve('somepath', 'image/jpeg')
        artpath = art.art_for_asin('xxxx')
        self.assertEqual(artpath, 'somepath')

    def test_main_interface_returns_amazon_art(self):
        art.urllib.urlretrieve = MockUrlRetrieve('anotherpath', 'image/jpeg')
        album = {'asin': 'xxxx'}
        artpath = art.art_for_album(album)
        self.assertEqual(artpath, 'anotherpath')

    def test_main_interface_returns_none_for_missing_asin(self):
        album = {'asin': None}
        artpath = art.art_for_album(album)
        self.assertEqual(artpath, None)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
