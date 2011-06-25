# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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

import _common
from beets.autotag import art
import os
import shutil

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

class FSArtTest(unittest.TestCase):
    def setUp(self):
        self.dpath = os.path.join(_common.RSRC, 'arttest')
        os.mkdir(self.dpath)
    def tearDown(self):
        shutil.rmtree(self.dpath)

    def test_finds_jpg_in_directory(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        fn = art.art_in_path(self.dpath)
        self.assertEqual(fn, os.path.join(self.dpath, 'a.jpg'))

    def test_appropriately_named_file_takes_precedence(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        _common.touch(os.path.join(self.dpath, 'cover.jpg'))
        fn = art.art_in_path(self.dpath)
        self.assertEqual(fn, os.path.join(self.dpath, 'cover.jpg'))

    def test_non_image_file_not_identified(self):
        _common.touch(os.path.join(self.dpath, 'a.txt'))
        fn = art.art_in_path(self.dpath)
        self.assertEqual(fn, None)

class CombinedTest(unittest.TestCase):
    def setUp(self):
        self.dpath = os.path.join(_common.RSRC, 'arttest')
        os.mkdir(self.dpath)
    def tearDown(self):
        shutil.rmtree(self.dpath)

    def test_main_interface_returns_amazon_art(self):
        art.urllib.urlretrieve = MockUrlRetrieve('anotherpath', 'image/jpeg')
        album = {'asin': 'xxxx'}
        artpath = art.art_for_album(album, None)
        self.assertEqual(artpath, 'anotherpath')

    def test_main_interface_returns_none_for_missing_asin_and_path(self):
        album = {'asin': None}
        artpath = art.art_for_album(album, None)
        self.assertEqual(artpath, None)

    def test_main_interface_gives_precedence_to_fs_art(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        art.urllib.urlretrieve = MockUrlRetrieve('anotherpath', 'image/jpeg')
        album = {'asin': 'xxxx'}
        artpath = art.art_for_album(album, self.dpath)
        self.assertEqual(artpath, os.path.join(self.dpath, 'a.jpg'))

    def test_main_interface_falls_back_to_amazon(self):
        art.urllib.urlretrieve = MockUrlRetrieve('anotherpath', 'image/jpeg')
        album = {'asin': 'xxxx'}
        artpath = art.art_for_album(album, self.dpath)
        self.assertEqual(artpath, 'anotherpath')

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
