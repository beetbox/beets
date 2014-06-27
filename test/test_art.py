# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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

import os
import shutil

import responses

import _common
from _common import unittest
from beetsplug import fetchart
from beets.autotag import AlbumInfo, AlbumMatch
from beets import library
from beets import importer
from beets import config


class FetchImageTest(_common.TestCase):
    @responses.activate
    def run(self, *args, **kwargs):
        super(FetchImageTest, self).run(*args, **kwargs)

    def mock_response(self, content_type):
        responses.add(responses.GET, 'http://example.com', content_type=content_type)

    def test_invalid_type_returns_none(self):
        self.mock_response('image/watercolour')
        artpath = fetchart._fetch_image('http://example.com')
        self.assertEqual(artpath, None)

    def test_jpeg_type_returns_path(self):
        self.mock_response('image/jpeg')
        artpath = fetchart._fetch_image('http://example.com')
        self.assertNotEqual(artpath, None)


class FSArtTest(_common.TestCase):
    def setUp(self):
        super(FSArtTest, self).setUp()
        self.dpath = os.path.join(self.temp_dir, 'arttest')
        os.mkdir(self.dpath)

    def test_finds_jpg_in_directory(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        fn = fetchart.art_in_path(self.dpath, ('art',), False)
        self.assertEqual(fn, os.path.join(self.dpath, 'a.jpg'))

    def test_appropriately_named_file_takes_precedence(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        _common.touch(os.path.join(self.dpath, 'art.jpg'))
        fn = fetchart.art_in_path(self.dpath, ('art',), False)
        self.assertEqual(fn, os.path.join(self.dpath, 'art.jpg'))

    def test_non_image_file_not_identified(self):
        _common.touch(os.path.join(self.dpath, 'a.txt'))
        fn = fetchart.art_in_path(self.dpath, ('art',), False)
        self.assertEqual(fn, None)

    def test_cautious_skips_fallback(self):
        _common.touch(os.path.join(self.dpath, 'a.jpg'))
        fn = fetchart.art_in_path(self.dpath, ('art',), True)
        self.assertEqual(fn, None)

    def test_empty_dir(self):
        fn = fetchart.art_in_path(self.dpath, ('art',), True)
        self.assertEqual(fn, None)

    def test_precedence_amongst_correct_files(self):
        _common.touch(os.path.join(self.dpath, 'back.jpg'))
        _common.touch(os.path.join(self.dpath, 'front.jpg'))
        _common.touch(os.path.join(self.dpath, 'front-cover.jpg'))
        fn = fetchart.art_in_path(self.dpath, ('cover', 'front', 'back'), False)
        self.assertEqual(fn, os.path.join(self.dpath, 'front-cover.jpg'))

class CombinedTest(_common.TestCase):
    ASIN = 'xxxx'
    MBID = 'releaseid'
    AMAZON_URL = 'http://images.amazon.com/images/P/{0}.01.LZZZZZZZ.jpg'.format(ASIN)
    AAO_URL = 'http://www.albumart.org/index_detail.php?asin={0}'.format(ASIN)
    CAA_URL = 'http://coverartarchive.org/release/{0}/front-500.jpg'.format(MBID)

    def setUp(self):
        super(CombinedTest, self).setUp()
        self.dpath = os.path.join(self.temp_dir, 'arttest')
        os.mkdir(self.dpath)

        # Set up configuration.
        fetchart.FetchArtPlugin()

    @responses.activate
    def run(self, *args, **kwargs):
        super(CombinedTest, self).run(*args, **kwargs)

    def mock_response(self, url, content_type='image/jpeg'):
        responses.add(responses.GET, url, content_type=content_type)

    def test_main_interface_returns_amazon_art(self):
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        artpath = fetchart.art_for_album(album, None)
        self.assertNotEqual(artpath, None)

    def test_main_interface_returns_none_for_missing_asin_and_path(self):
        album = _common.Bag()
        artpath = fetchart.art_for_album(album, None)
        self.assertEqual(artpath, None)

    def test_main_interface_gives_precedence_to_fs_art(self):
        _common.touch(os.path.join(self.dpath, 'art.jpg'))
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        artpath = fetchart.art_for_album(album, [self.dpath])
        self.assertEqual(artpath, os.path.join(self.dpath, 'art.jpg'))

    def test_main_interface_falls_back_to_amazon(self):
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        artpath = fetchart.art_for_album(album, [self.dpath])
        self.assertNotEqual(artpath, None)
        self.assertFalse(artpath.startswith(self.dpath))

    def test_main_interface_tries_amazon_before_aao(self):
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        fetchart.art_for_album(album, [self.dpath])
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.url, self.AMAZON_URL)

    def test_main_interface_falls_back_to_aao(self):
        self.mock_response(self.AMAZON_URL, content_type='text/html')
        album = _common.Bag(asin=self.ASIN)
        fetchart.art_for_album(album, [self.dpath])
        self.assertEqual(responses.calls[-1].request.url, self.AAO_URL)

    def test_main_interface_uses_caa_when_mbid_available(self):
        self.mock_response(self.CAA_URL)
        album = _common.Bag(mb_albumid=self.MBID, asin=self.ASIN)
        artpath = fetchart.art_for_album(album, None)
        self.assertNotEqual(artpath, None)
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.url, self.CAA_URL)

    def test_local_only_does_not_access_network(self):
        album = _common.Bag(mb_albumid=self.MBID, asin=self.ASIN)
        artpath = fetchart.art_for_album(album, [self.dpath], local_only=True)
        self.assertEqual(artpath, None)
        self.assertEqual(len(responses.calls), 0)

    def test_local_only_gets_fs_image(self):
        _common.touch(os.path.join(self.dpath, 'art.jpg'))
        album = _common.Bag(mb_albumid=self.MBID, asin=self.ASIN)
        artpath = fetchart.art_for_album(album, [self.dpath], None, local_only=True)
        self.assertEqual(artpath, os.path.join(self.dpath, 'art.jpg'))
        self.assertEqual(len(responses.calls), 0)


class AAOTest(_common.TestCase):
    ASIN = 'xxxx'
    AAO_URL = 'http://www.albumart.org/index_detail.php?asin={0}'.format(ASIN)

    @responses.activate
    def run(self, *args, **kwargs):
        super(AAOTest, self).run(*args, **kwargs)

    def mock_response(self, url, body):
        responses.add(responses.GET, url, body=body, content_type='text/html',
                      match_querystring=True)

    def test_aao_scraper_finds_image(self):
        body = """
        <br />
        <a href="TARGET_URL" title="View larger image" class="thickbox" style="color: #7E9DA2; text-decoration:none;">
        <img src="http://www.albumart.org/images/zoom-icon.jpg" alt="View larger image" width="17" height="15"  border="0"/></a>
        """
        self.mock_response(self.AAO_URL, body)
        res = fetchart.aao_art(self.ASIN)
        self.assertEqual(res, 'TARGET_URL')

    def test_aao_scraper_returns_none_when_no_image_present(self):
        self.mock_response(self.AAO_URL, 'blah blah')
        res = fetchart.aao_art(self.ASIN)
        self.assertEqual(res, None)


class GoogleImageTest(_common.TestCase):

    _google_url = 'https://ajax.googleapis.com/ajax/services/search/images'

    @responses.activate
    def run(self, *args, **kwargs):
        super(GoogleImageTest, self).run(*args, **kwargs)

    def mock_response(self, url, json):
        responses.add(responses.GET, url, body=json,
                      content_type='application/json')

    def test_google_art_finds_image(self):
        album = _common.Bag(albumartist="some artist", album="some album")
        json = """{"responseData": {"results":
            [{"unescapedUrl": "url_to_the_image"}]}}"""
        self.mock_response(self._google_url, json)
        result_url = fetchart.google_art(album)
        self.assertEqual(result_url, 'url_to_the_image')

    def test_google_art_dont_finds_image(self):
        album = _common.Bag(albumartist="some artist", album="some album")
        json = """bla blup"""
        self.mock_response(self._google_url, json)
        result_url = fetchart.google_art(album)
        self.assertEqual(result_url, None)


class ArtImporterTest(_common.TestCase):
    def setUp(self):
        super(ArtImporterTest, self).setUp()

        # Mock the album art fetcher to always return our test file.
        self.art_file = os.path.join(self.temp_dir, 'tmpcover.jpg')
        _common.touch(self.art_file)
        self.old_afa = fetchart.art_for_album
        self.afa_response = self.art_file
        def art_for_album(i, p, maxwidth=None, local_only=False):
            return self.afa_response
        fetchart.art_for_album = art_for_album

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

        # The plugin and import configuration.
        self.plugin = fetchart.FetchArtPlugin()
        self.session = _common.import_session(self.lib)

        # Import task for the coroutine.
        self.task = importer.ImportTask(None, None, [self.i])
        self.task.is_album = True
        self.task.album = self.album
        info = AlbumInfo(
            album = 'some album',
            album_id = 'albumid',
            artist = 'some artist',
            artist_id = 'artistid',
            tracks = [],
        )
        self.task.set_choice(AlbumMatch(0, info, {}, set(), set()))

    def tearDown(self):
        self.lib._connection().close()
        super(ArtImporterTest, self).tearDown()
        fetchart.art_for_album = self.old_afa

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


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
