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
from beets.autotag import AlbumInfo
import os
import shutil
import StringIO

class MockHeaders(object):
    def __init__(self, typeval):
        self.typeval = typeval
    def gettype(self):
        return self.typeval
class MockUrlRetrieve(object):
    def __init__(self, pathval, typeval):
        self.pathval = pathval
        self.headers = MockHeaders(typeval)
        self.fetched = None
    def __call__(self, url):
        self.fetched = url
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
        self.old_urlopen = art.urllib.urlopen
        art.urllib.urlopen = self._urlopen
        self.page_text = ""
    def tearDown(self):
        shutil.rmtree(self.dpath)
        art.urllib.urlopen = self.old_urlopen

    def _urlopen(self, url):
        self.urlopen_called = True
        return StringIO.StringIO(self.page_text)

    def test_main_interface_returns_amazon_art(self):
        art.urllib.urlretrieve = MockUrlRetrieve('anotherpath', 'image/jpeg')
        album = AlbumInfo(None, None, None, None, None, asin='xxxx')
        artpath = art.art_for_album(album, None)
        self.assertEqual(artpath, 'anotherpath')

    def test_main_interface_returns_none_for_missing_asin_and_path(self):
        album = AlbumInfo(None, None, None, None, None, asin=None)
        artpath = art.art_for_album(album, None)
        self.assertEqual(artpath, None)

    def test_main_interface_gives_precedence_to_fs_art(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        art.urllib.urlretrieve = MockUrlRetrieve('anotherpath', 'image/jpeg')
        album = AlbumInfo(None, None, None, None, None, asin='xxxx')
        artpath = art.art_for_album(album, self.dpath)
        self.assertEqual(artpath, os.path.join(self.dpath, 'a.jpg'))

    def test_main_interface_falls_back_to_amazon(self):
        art.urllib.urlretrieve = MockUrlRetrieve('anotherpath', 'image/jpeg')
        album = AlbumInfo(None, None, None, None, None, asin='xxxx')
        artpath = art.art_for_album(album, self.dpath)
        self.assertEqual(artpath, 'anotherpath')

    def test_main_interface_tries_amazon_before_aao(self):
        self.urlopen_called = False
        art.urllib.urlretrieve = MockUrlRetrieve('anotherpath', 'image/jpeg')
        album = AlbumInfo(None, None, None, None, None, asin='xxxx')
        art.art_for_album(album, self.dpath)
        self.assertFalse(self.urlopen_called)

    def test_main_interface_falls_back_to_aao(self):
        self.urlopen_called = False
        art.urllib.urlretrieve = MockUrlRetrieve('anotherpath', 'text/html')
        album = AlbumInfo(None, None, None, None, None, asin='xxxx')
        art.art_for_album(album, self.dpath)
        self.assertTrue(self.urlopen_called)

class AAOTest(unittest.TestCase):
    def setUp(self):
        self.old_urlopen = art.urllib.urlopen
        self.old_urlretrieve = art.urllib.urlretrieve
        art.urllib.urlopen = self._urlopen
        self.retriever = MockUrlRetrieve('somepath', 'image/jpeg')
        art.urllib.urlretrieve = self.retriever
        self.page_text = ''
    def tearDown(self):
        art.urllib.urlopen = self.old_urlopen
        art.urllib.urlretrieve = self.old_urlretrieve

    def _urlopen(self, url):
        return StringIO.StringIO(self.page_text)

    def test_aao_scraper_finds_image(self):
        self.page_text = """
        <br />
        <a href="TARGET_URL" title="View larger image" class="thickbox" style="color: #7E9DA2; text-decoration:none;">
        <img src="http://www.albumart.org/images/zoom-icon.jpg" alt="View larger image" width="17" height="15"  border="0"/></a>
        """
        res = art.aao_art('x')
        self.assertEqual(self.retriever.fetched, 'TARGET_URL')
        self.assertEqual(res, 'somepath')

    def test_aao_scraper_returns_none_when_no_image_present(self):
        self.page_text = "blah blah"
        res = art.aao_art('x')
        self.assertEqual(self.retriever.fetched, None)
        self.assertEqual(res, None)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
