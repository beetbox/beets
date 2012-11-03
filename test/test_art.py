# This file is part of beets.
# Copyright 2012, Adrian Sampson.
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

import _common
from _common import unittest
from beetsplug import fetchart
from beets.autotag import AlbumInfo, AlbumMatch
from beets import library
from beets import importer
import os
import shutil
import StringIO

class MockHeaders(object):
    def __init__(self, typeval):
        self.typeval = typeval
    def gettype(self):
        return self.typeval
class MockUrlRetrieve(object):
    def __init__(self, typeval, pathval='fetched_path'):
        self.pathval = pathval
        self.headers = MockHeaders(typeval)
        self.fetched = None
    def __call__(self, url, filename=None):
        self.fetched = url
        return filename or self.pathval, self.headers

class FetchImageTest(unittest.TestCase):
    def test_invalid_type_returns_none(self):
        fetchart.urllib.urlretrieve = MockUrlRetrieve('')
        artpath = fetchart._fetch_image('http://example.com')
        self.assertEqual(artpath, None)

    def test_jpeg_type_returns_path(self):
        fetchart.urllib.urlretrieve = MockUrlRetrieve('image/jpeg')
        artpath = fetchart._fetch_image('http://example.com')
        self.assertNotEqual(artpath, None)

class FSArtTest(unittest.TestCase):
    def setUp(self):
        self.dpath = os.path.join(_common.RSRC, 'arttest')
        os.mkdir(self.dpath)
    def tearDown(self):
        shutil.rmtree(self.dpath)

    def test_finds_jpg_in_directory(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        fn = fetchart.art_in_path(self.dpath)
        self.assertEqual(fn, os.path.join(self.dpath, 'a.jpg'))

    def test_appropriately_named_file_takes_precedence(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        _common.touch(os.path.join(self.dpath, 'cover.jpg'))
        fn = fetchart.art_in_path(self.dpath)
        self.assertEqual(fn, os.path.join(self.dpath, 'cover.jpg'))

    def test_non_image_file_not_identified(self):
        _common.touch(os.path.join(self.dpath, 'a.txt'))
        fn = fetchart.art_in_path(self.dpath)
        self.assertEqual(fn, None)

class CombinedTest(unittest.TestCase):
    def setUp(self):
        self.dpath = os.path.join(_common.RSRC, 'arttest')
        os.mkdir(self.dpath)
        self.old_urlopen = fetchart.urllib.urlopen
        fetchart.urllib.urlopen = self._urlopen
        self.page_text = ""
        self.urlopen_called = False
    def tearDown(self):
        shutil.rmtree(self.dpath)
        fetchart.urllib.urlopen = self.old_urlopen

    def _urlopen(self, url):
        self.urlopen_called = True
        self.fetched_url = url
        return StringIO.StringIO(self.page_text)

    def test_main_interface_returns_amazon_art(self):
        fetchart.urllib.urlretrieve = MockUrlRetrieve('image/jpeg')
        album = _common.Bag(asin='xxxx')
        artpath = fetchart.art_for_album(album, None)
        self.assertNotEqual(artpath, None)

    def test_main_interface_returns_none_for_missing_asin_and_path(self):
        album = _common.Bag()
        artpath = fetchart.art_for_album(album, None)
        self.assertEqual(artpath, None)

    def test_main_interface_gives_precedence_to_fs_art(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        fetchart.urllib.urlretrieve = MockUrlRetrieve('image/jpeg')
        album = _common.Bag(asin='xxxx')
        artpath = fetchart.art_for_album(album, self.dpath)
        self.assertEqual(artpath, os.path.join(self.dpath, 'a.jpg'))

    def test_main_interface_falls_back_to_amazon(self):
        fetchart.urllib.urlretrieve = MockUrlRetrieve('image/jpeg')
        album = _common.Bag(asin='xxxx')
        artpath = fetchart.art_for_album(album, self.dpath)
        self.assertNotEqual(artpath, None)
        self.assertFalse(artpath.startswith(self.dpath))

    def test_main_interface_tries_amazon_before_aao(self):
        fetchart.urllib.urlretrieve = MockUrlRetrieve('image/jpeg')
        album = _common.Bag(asin='xxxx')
        fetchart.art_for_album(album, self.dpath)
        self.assertFalse(self.urlopen_called)

    def test_main_interface_falls_back_to_aao(self):
        fetchart.urllib.urlretrieve = MockUrlRetrieve('text/html')
        album = _common.Bag(asin='xxxx')
        fetchart.art_for_album(album, self.dpath)
        self.assertTrue(self.urlopen_called)

    def test_main_interface_uses_caa_when_mbid_available(self):
        mock_retrieve = MockUrlRetrieve('image/jpeg')
        fetchart.urllib.urlretrieve = mock_retrieve
        album = _common.Bag(mb_albumid='releaseid', asin='xxxx')
        artpath = fetchart.art_for_album(album, None)
        self.assertNotEqual(artpath, None)
        self.assertTrue('coverartarchive.org' in mock_retrieve.fetched)

    def test_local_only_does_not_access_network(self):
        mock_retrieve = MockUrlRetrieve('image/jpeg')
        fetchart.urllib.urlretrieve = mock_retrieve
        album = _common.Bag(mb_albumid='releaseid', asin='xxxx')
        artpath = fetchart.art_for_album(album, self.dpath, local_only=True)
        self.assertEqual(artpath, None)
        self.assertFalse(self.urlopen_called)
        self.assertFalse(mock_retrieve.fetched)

    def test_local_only_gets_fs_image(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        mock_retrieve = MockUrlRetrieve('image/jpeg')
        fetchart.urllib.urlretrieve = mock_retrieve
        album = _common.Bag(mb_albumid='releaseid', asin='xxxx')
        artpath = fetchart.art_for_album(album, self.dpath, local_only=True)
        self.assertEqual(artpath, os.path.join(self.dpath, 'a.jpg'))
        self.assertFalse(self.urlopen_called)
        self.assertFalse(mock_retrieve.fetched)

class AAOTest(unittest.TestCase):
    def setUp(self):
        self.old_urlopen = fetchart.urllib.urlopen
        fetchart.urllib.urlopen = self._urlopen
        self.page_text = ''
    def tearDown(self):
        fetchart.urllib.urlopen = self.old_urlopen

    def _urlopen(self, url):
        return StringIO.StringIO(self.page_text)

    def test_aao_scraper_finds_image(self):
        self.page_text = """
        <br />
        <a href="TARGET_URL" title="View larger image" class="thickbox" style="color: #7E9DA2; text-decoration:none;">
        <img src="http://www.albumart.org/images/zoom-icon.jpg" alt="View larger image" width="17" height="15"  border="0"/></a>
        """
        res = fetchart.aao_art('x')
        self.assertEqual(res, 'TARGET_URL')

    def test_aao_scraper_returns_none_when_no_image_present(self):
        self.page_text = "blah blah"
        res = fetchart.aao_art('x')
        self.assertEqual(res, None)

class ArtImporterTest(unittest.TestCase, _common.ExtraAsserts):
    def setUp(self):
        # Mock the album art fetcher to always return our test file.
        self.art_file = os.path.join(_common.RSRC, 'tmpcover.jpg')
        _common.touch(self.art_file)
        self.old_afa = fetchart.art_for_album
        self.afa_response = self.art_file
        def art_for_album(i, p, maxwidth=None, local_only=False):
            return self.afa_response
        fetchart.art_for_album = art_for_album

        # Test library.
        self.libpath = os.path.join(_common.RSRC, 'tmplib.blb')
        self.libdir = os.path.join(_common.RSRC, 'tmplib')
        os.mkdir(self.libdir)
        os.mkdir(os.path.join(self.libdir, 'album'))
        itempath = os.path.join(self.libdir, 'album', 'test.mp3')
        shutil.copyfile(os.path.join(_common.RSRC, 'full.mp3'), itempath)
        self.lib = library.Library(self.libpath)
        self.i = _common.item()
        self.i.path = itempath
        self.album = self.lib.add_album([self.i])
        self.lib._connection().commit()

        # The plugin and import configuration.
        self.plugin = fetchart.FetchArtPlugin()
        self.config = _common.iconfig(self.lib)

        # Import task for the coroutine.
        self.task = importer.ImportTask(None, None, [self.i])
        self.task.is_album = True
        self.task.album_id = self.album.id
        info = AlbumInfo(
            album = 'some album',
            album_id = 'albumid',
            artist = 'some artist',
            artist_id = 'artistid',
            tracks = [],
        )
        self.task.set_choice(AlbumMatch(0, info, {}, set(), set()))

    def tearDown(self):
        fetchart.art_for_album = self.old_afa
        if os.path.exists(self.art_file):
            os.remove(self.art_file)
        if os.path.exists(self.libpath):
            os.remove(self.libpath)
        if os.path.exists(self.libdir):
            shutil.rmtree(self.libdir)

    def _fetch_art(self, should_exist):
        """Execute the fetch_art coroutine for the task and return the
        album's resulting artpath. ``should_exist`` specifies whether to
        assert that art path was set (to the correct value) or or that
        the path was not set.
        """
        # Execute the two relevant parts of the importer.
        self.plugin.fetch_art(self.config, self.task)
        self.plugin.assign_art(self.config, self.task)

        artpath = self.lib.albums()[0].artpath
        if should_exist:
            self.assertEqual(artpath,
                os.path.join(os.path.dirname(self.i.path), 'cover.jpg'))
            self.assertExists(artpath)
        else:
            self.assertEqual(artpath, None)
        return artpath

    def test_fetch_art(self):
        assert not self.lib.albums()[0].artpath
        self._fetch_art(True)

    def test_art_not_found(self):
        self.afa_response = None
        self._fetch_art(False)

    def test_no_art_for_singleton(self):
        self.task.is_album = False
        self._fetch_art(False)

    def test_leave_original_file_in_place(self):
        self._fetch_art(True)
        self.assertExists(self.art_file)

    def test_delete_original_file(self):
        self.config.delete = True
        self._fetch_art(True)
        self.assertNotExists(self.art_file)

    def test_move_original_file(self):
        self.config.move = True
        self._fetch_art(True)
        self.assertNotExists(self.art_file)

    def test_do_not_delete_original_if_already_in_place(self):
        artdest = os.path.join(os.path.dirname(self.i.path), 'cover.jpg')
        shutil.copyfile(self.art_file, artdest)
        self.afa_response = artdest
        self._fetch_art(True)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
