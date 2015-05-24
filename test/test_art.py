# This file is part of beets.
# Copyright 2015, Adrian Sampson.
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

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import os
import shutil

import responses

from test import _common
from test._common import unittest
from beetsplug import fetchart
from beets.autotag import AlbumInfo, AlbumMatch
from beets import library
from beets import importer
from beets import config
from beets import logging
from beets.util.artresizer import ArtResizer, WEBPROXY


logger = logging.getLogger('beets.test_art')


class UseThePlugin(_common.TestCase):
    def setUp(self):
        super(UseThePlugin, self).setUp()
        self.plugin = fetchart.FetchArtPlugin()


class FetchImageTest(UseThePlugin):
    @responses.activate
    def run(self, *args, **kwargs):
        super(FetchImageTest, self).run(*args, **kwargs)

    def mock_response(self, content_type):
        responses.add(responses.GET, 'http://example.com',
                      content_type=content_type)

    def test_invalid_type_returns_none(self):
        self.mock_response('image/watercolour')
        artpath = self.plugin._fetch_image('http://example.com')
        self.assertEqual(artpath, None)

    def test_jpeg_type_returns_path(self):
        self.mock_response('image/jpeg')
        artpath = self.plugin._fetch_image('http://example.com')
        self.assertNotEqual(artpath, None)


class FSArtTest(_common.TestCase):
    def setUp(self):
        super(FSArtTest, self).setUp()
        self.dpath = os.path.join(self.temp_dir, 'arttest')
        os.mkdir(self.dpath)

        self.source = fetchart.FileSystem(logger)

    def test_finds_jpg_in_directory(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        fn = self.source.get(self.dpath, ('art',), False)
        self.assertEqual(fn, os.path.join(self.dpath, 'a.jpg'))

    def test_appropriately_named_file_takes_precedence(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        _common.touch(os.path.join(self.dpath, 'art.jpg'))
        fn = self.source.get(self.dpath, ('art',), False)
        self.assertEqual(fn, os.path.join(self.dpath, 'art.jpg'))

    def test_non_image_file_not_identified(self):
        _common.touch(os.path.join(self.dpath, 'a.txt'))
        fn = self.source.get(self.dpath, ('art',), False)
        self.assertEqual(fn, None)

    def test_cautious_skips_fallback(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        fn = self.source.get(self.dpath, ('art',), True)
        self.assertEqual(fn, None)

    def test_empty_dir(self):
        fn = self.source.get(self.dpath, ('art',), True)
        self.assertEqual(fn, None)

    def test_precedence_amongst_correct_files(self):
        _common.touch(os.path.join(self.dpath, 'back.jpg'))
        _common.touch(os.path.join(self.dpath, 'front.jpg'))
        _common.touch(os.path.join(self.dpath, 'front-cover.jpg'))
        fn = self.source.get(self.dpath, ('cover', 'front', 'back'), False)
        self.assertEqual(fn, os.path.join(self.dpath, 'front-cover.jpg'))


class CombinedTest(UseThePlugin):
    ASIN = 'xxxx'
    MBID = 'releaseid'
    AMAZON_URL = 'http://images.amazon.com/images/P/{0}.01.LZZZZZZZ.jpg' \
                 .format(ASIN)
    AAO_URL = 'http://www.albumart.org/index_detail.php?asin={0}' \
              .format(ASIN)
    CAA_URL = 'http://coverartarchive.org/release/{0}/front' \
              .format(MBID)

    def setUp(self):
        super(CombinedTest, self).setUp()
        self.dpath = os.path.join(self.temp_dir, 'arttest')
        os.mkdir(self.dpath)

    @responses.activate
    def run(self, *args, **kwargs):
        super(CombinedTest, self).run(*args, **kwargs)

    def mock_response(self, url, content_type='image/jpeg'):
        responses.add(responses.GET, url, content_type=content_type)

    def test_main_interface_returns_amazon_art(self):
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        artpath = self.plugin.art_for_album(album, None)
        self.assertNotEqual(artpath, None)

    def test_main_interface_returns_none_for_missing_asin_and_path(self):
        album = _common.Bag()
        artpath = self.plugin.art_for_album(album, None)
        self.assertEqual(artpath, None)

    def test_main_interface_gives_precedence_to_fs_art(self):
        _common.touch(os.path.join(self.dpath, 'art.jpg'))
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        artpath = self.plugin.art_for_album(album, [self.dpath])
        self.assertEqual(artpath, os.path.join(self.dpath, 'art.jpg'))

    def test_main_interface_falls_back_to_amazon(self):
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        artpath = self.plugin.art_for_album(album, [self.dpath])
        self.assertNotEqual(artpath, None)
        self.assertFalse(artpath.startswith(self.dpath))

    def test_main_interface_tries_amazon_before_aao(self):
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        self.plugin.art_for_album(album, [self.dpath])
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.url, self.AMAZON_URL)

    def test_main_interface_falls_back_to_aao(self):
        self.mock_response(self.AMAZON_URL, content_type='text/html')
        album = _common.Bag(asin=self.ASIN)
        self.plugin.art_for_album(album, [self.dpath])
        self.assertEqual(responses.calls[-1].request.url, self.AAO_URL)

    def test_main_interface_uses_caa_when_mbid_available(self):
        self.mock_response(self.CAA_URL)
        album = _common.Bag(mb_albumid=self.MBID, asin=self.ASIN)
        artpath = self.plugin.art_for_album(album, None)
        self.assertNotEqual(artpath, None)
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.url, self.CAA_URL)

    def test_local_only_does_not_access_network(self):
        album = _common.Bag(mb_albumid=self.MBID, asin=self.ASIN)
        artpath = self.plugin.art_for_album(album, [self.dpath],
                                            local_only=True)
        self.assertEqual(artpath, None)
        self.assertEqual(len(responses.calls), 0)

    def test_local_only_gets_fs_image(self):
        _common.touch(os.path.join(self.dpath, 'art.jpg'))
        album = _common.Bag(mb_albumid=self.MBID, asin=self.ASIN)
        artpath = self.plugin.art_for_album(album, [self.dpath],
                                            local_only=True)
        self.assertEqual(artpath, os.path.join(self.dpath, 'art.jpg'))
        self.assertEqual(len(responses.calls), 0)


class AAOTest(_common.TestCase):
    ASIN = 'xxxx'
    AAO_URL = 'http://www.albumart.org/index_detail.php?asin={0}'.format(ASIN)

    def setUp(self):
        super(AAOTest, self).setUp()
        self.source = fetchart.AlbumArtOrg(logger)

    @responses.activate
    def run(self, *args, **kwargs):
        super(AAOTest, self).run(*args, **kwargs)

    def mock_response(self, url, body):
        responses.add(responses.GET, url, body=body, content_type='text/html',
                      match_querystring=True)

    def test_aao_scraper_finds_image(self):
        body = b"""
        <br />
        <a href="TARGET_URL" title="View larger image"
           class="thickbox" style="color: #7E9DA2; text-decoration:none;">
        <img src="http://www.albumart.org/images/zoom-icon.jpg"
             alt="View larger image" width="17" height="15"  border="0"/></a>
        """
        self.mock_response(self.AAO_URL, body)
        album = _common.Bag(asin=self.ASIN)
        res = self.source.get(album)
        self.assertEqual(list(res)[0], 'TARGET_URL')

    def test_aao_scraper_returns_no_result_when_no_image_present(self):
        self.mock_response(self.AAO_URL, b'blah blah')
        album = _common.Bag(asin=self.ASIN)
        res = self.source.get(album)
        self.assertEqual(list(res), [])


class GoogleImageTest(_common.TestCase):

    _google_url = 'https://ajax.googleapis.com/ajax/services/search/images'

    def setUp(self):
        super(GoogleImageTest, self).setUp()
        self.source = fetchart.GoogleImages(logger)

    @responses.activate
    def run(self, *args, **kwargs):
        super(GoogleImageTest, self).run(*args, **kwargs)

    def mock_response(self, url, json):
        responses.add(responses.GET, url, body=json,
                      content_type='application/json')

    def test_google_art_finds_image(self):
        album = _common.Bag(albumartist="some artist", album="some album")
        json = b"""{"responseData": {"results":
            [{"unescapedUrl": "url_to_the_image"}]}}"""
        self.mock_response(self._google_url, json)
        result_url = self.source.get(album)
        self.assertEqual(list(result_url)[0], 'url_to_the_image')

    def test_google_art_dont_finds_image(self):
        album = _common.Bag(albumartist="some artist", album="some album")
        json = b"""bla blup"""
        self.mock_response(self._google_url, json)
        result_url = self.source.get(album)
        self.assertEqual(list(result_url), [])


class ArtImporterTest(UseThePlugin):
    def setUp(self):
        super(ArtImporterTest, self).setUp()

        # Mock the album art fetcher to always return our test file.
        self.art_file = os.path.join(self.temp_dir, 'tmpcover.jpg')
        _common.touch(self.art_file)
        self.old_afa = self.plugin.art_for_album
        self.afa_response = self.art_file

        def art_for_album(i, p, local_only=False):
            return self.afa_response

        self.plugin.art_for_album = art_for_album

        # Test library.
        self.libpath = os.path.join(self.temp_dir, 'tmplib.blb')
        self.libdir = os.path.join(self.temp_dir, 'tmplib')
        os.mkdir(self.libdir)
        os.mkdir(os.path.join(self.libdir, 'album'))
        itempath = os.path.join(self.libdir, 'album', 'test.mp3')
        shutil.copyfile(os.path.join(_common.RSRC, 'full.mp3'), itempath)
        self.lib = library.Library(self.libpath)
        self.i = _common.item()
        self.i.path = itempath
        self.album = self.lib.add_album([self.i])
        self.lib._connection().commit()

        # The import configuration.
        self.session = _common.import_session(self.lib)

        # Import task for the coroutine.
        self.task = importer.ImportTask(None, None, [self.i])
        self.task.is_album = True
        self.task.album = self.album
        info = AlbumInfo(
            album='some album',
            album_id='albumid',
            artist='some artist',
            artist_id='artistid',
            tracks=[],
        )
        self.task.set_choice(AlbumMatch(0, info, {}, set(), set()))

    def tearDown(self):
        self.lib._connection().close()
        super(ArtImporterTest, self).tearDown()
        self.plugin.art_for_album = self.old_afa

    def _fetch_art(self, should_exist):
        """Execute the fetch_art coroutine for the task and return the
        album's resulting artpath. ``should_exist`` specifies whether to
        assert that art path was set (to the correct value) or or that
        the path was not set.
        """
        # Execute the two relevant parts of the importer.
        self.plugin.fetch_art(self.session, self.task)
        self.plugin.assign_art(self.session, self.task)

        artpath = self.lib.albums()[0].artpath
        if should_exist:
            self.assertEqual(
                artpath,
                os.path.join(os.path.dirname(self.i.path), 'cover.jpg')
            )
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
        config['import']['delete'] = True
        self._fetch_art(True)
        self.assertNotExists(self.art_file)

    def test_move_original_file(self):
        config['import']['move'] = True
        self._fetch_art(True)
        self.assertNotExists(self.art_file)

    def test_do_not_delete_original_if_already_in_place(self):
        artdest = os.path.join(os.path.dirname(self.i.path), 'cover.jpg')
        shutil.copyfile(self.art_file, artdest)
        self.afa_response = artdest
        self._fetch_art(True)


class ArtForAlbumTest(UseThePlugin):
    """ Tests that fetchart.art_for_album respects the size
    configuration (e.g., minwidth, enforce_ratio)
    """

    IMG_225x225 = os.path.join(_common.RSRC, 'abbey.jpg')
    IMG_348x348 = os.path.join(_common.RSRC, 'abbey-different.jpg')
    IMG_500x490 = os.path.join(_common.RSRC, 'abbey-similar.jpg')

    def setUp(self):
        super(ArtForAlbumTest, self).setUp()

        self.old_fs_source_get = self.plugin.fs_source.get
        self.old_fetch_img = self.plugin._fetch_image
        self.old_source_urls = self.plugin._source_urls

        def fs_source_get(*_):
            return self.image_file

        def source_urls(_):
            return ['']

        def fetch_img(_):
            return self.image_file

        self.plugin.fs_source.get = fs_source_get
        self.plugin._source_urls = source_urls
        self.plugin._fetch_image = fetch_img

    def tearDown(self):
        self.plugin.fs_source.get = self.old_fs_source_get
        self.plugin._source_urls = self.old_source_urls
        self.plugin._fetch_image = self.old_fetch_img
        super(ArtForAlbumTest, self).tearDown()

    def _assertImageIsValidArt(self, image_file, should_exist):
        self.assertExists(image_file)
        self.image_file = image_file

        local_artpath = self.plugin.art_for_album(None, [''], True)
        remote_artpath = self.plugin.art_for_album(None, [], False)

        self.assertEqual(local_artpath, remote_artpath)

        if should_exist:
            self.assertEqual(local_artpath, self.image_file)
            self.assertExists(local_artpath)
            return local_artpath
        else:
            self.assertIsNone(local_artpath)

    def _require_backend(self):
        """Skip the test if the art resizer doesn't have ImageMagick or
        PIL (so comparisons and measurements are unavailable).
        """
        if ArtResizer.shared.method[0] == WEBPROXY:
            self.skipTest("ArtResizer has no local imaging backend available")

    def test_respect_minwidth(self):
        self._require_backend()
        self.plugin.minwidth = 300
        self._assertImageIsValidArt(self.IMG_225x225, False)
        self._assertImageIsValidArt(self.IMG_348x348, True)

    def test_respect_enforce_ratio_yes(self):
        self._require_backend()
        self.plugin.enforce_ratio = True
        self._assertImageIsValidArt(self.IMG_500x490, False)
        self._assertImageIsValidArt(self.IMG_225x225, True)

    def test_respect_enforce_ratio_no(self):
        self.plugin.enforce_ratio = False
        self._assertImageIsValidArt(self.IMG_500x490, True)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
