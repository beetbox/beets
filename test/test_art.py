# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

from __future__ import division, absolute_import, print_function

import os
import shutil
import unittest

import responses
from mock import patch

from test import _common
from test.helper import capture_log
from beetsplug import fetchart
from beets.autotag import AlbumInfo, AlbumMatch
from beets import config
from beets import library
from beets import importer
from beets import logging
from beets import util
from beets.util.artresizer import ArtResizer, WEBPROXY
from beets.util import confit


logger = logging.getLogger('beets.test_art')


class Settings():
    """Used to pass settings to the ArtSources when the plugin isn't fully
    instantiated.
    """
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class UseThePlugin(_common.TestCase):
    def setUp(self):
        super(UseThePlugin, self).setUp()
        self.plugin = fetchart.FetchArtPlugin()


class FetchImageHelper(_common.TestCase):
    """Helper mixin for mocking requests when fetching images
    with remote art sources.
    """
    @responses.activate
    def run(self, *args, **kwargs):
        super(FetchImageHelper, self).run(*args, **kwargs)

    IMAGEHEADER = {'image/jpeg': b'\x00' * 6 + b'JFIF',
                   'image/png': b'\211PNG\r\n\032\n', }

    def mock_response(self, url, content_type='image/jpeg', file_type=None):
        if file_type is None:
            file_type = content_type
        responses.add(responses.GET, url,
                      content_type=content_type,
                      # imghdr reads 32 bytes
                      body=self.IMAGEHEADER.get(
                          file_type, b'').ljust(32, b'\x00'))


class FetchImageTest(FetchImageHelper, UseThePlugin):
    URL = 'http://example.com/test.jpg'

    def setUp(self):
        super(FetchImageTest, self).setUp()
        self.dpath = os.path.join(self.temp_dir, b'arttest')
        self.source = fetchart.RemoteArtSource(logger, self.plugin.config)
        self.settings = Settings(maxwidth=0)
        self.candidate = fetchart.Candidate(logger, url=self.URL)

    def test_invalid_type_returns_none(self):
        self.mock_response(self.URL, 'image/watercolour')
        self.source.fetch_image(self.candidate, self.settings)
        self.assertEqual(self.candidate.path, None)

    def test_jpeg_type_returns_path(self):
        self.mock_response(self.URL, 'image/jpeg')
        self.source.fetch_image(self.candidate, self.settings)
        self.assertNotEqual(self.candidate.path, None)

    def test_extension_set_by_content_type(self):
        self.mock_response(self.URL, 'image/png')
        self.source.fetch_image(self.candidate, self.settings)
        self.assertEqual(os.path.splitext(self.candidate.path)[1], b'.png')
        self.assertExists(self.candidate.path)

    def test_does_not_rely_on_server_content_type(self):
        self.mock_response(self.URL, 'image/jpeg', 'image/png')
        self.source.fetch_image(self.candidate, self.settings)
        self.assertEqual(os.path.splitext(self.candidate.path)[1], b'.png')
        self.assertExists(self.candidate.path)


class FSArtTest(UseThePlugin):
    def setUp(self):
        super(FSArtTest, self).setUp()
        self.dpath = os.path.join(self.temp_dir, b'arttest')
        os.mkdir(self.dpath)

        self.source = fetchart.FileSystem(logger, self.plugin.config)
        self.settings = Settings(cautious=False,
                                 cover_names=('art',))

    def test_finds_jpg_in_directory(self):
        _common.touch(os.path.join(self.dpath, b'a.jpg'))
        candidate = next(self.source.get(None, self.settings, [self.dpath]))
        self.assertEqual(candidate.path, os.path.join(self.dpath, b'a.jpg'))

    def test_appropriately_named_file_takes_precedence(self):
        _common.touch(os.path.join(self.dpath, b'a.jpg'))
        _common.touch(os.path.join(self.dpath, b'art.jpg'))
        candidate = next(self.source.get(None, self.settings, [self.dpath]))
        self.assertEqual(candidate.path, os.path.join(self.dpath, b'art.jpg'))

    def test_non_image_file_not_identified(self):
        _common.touch(os.path.join(self.dpath, b'a.txt'))
        with self.assertRaises(StopIteration):
            next(self.source.get(None, self.settings, [self.dpath]))

    def test_cautious_skips_fallback(self):
        _common.touch(os.path.join(self.dpath, b'a.jpg'))
        self.settings.cautious = True
        with self.assertRaises(StopIteration):
            next(self.source.get(None, self.settings, [self.dpath]))

    def test_empty_dir(self):
        with self.assertRaises(StopIteration):
            next(self.source.get(None, self.settings, [self.dpath]))

    def test_precedence_amongst_correct_files(self):
        images = [b'front-cover.jpg', b'front.jpg', b'back.jpg']
        paths = [os.path.join(self.dpath, i) for i in images]
        for p in paths:
            _common.touch(p)
        self.settings.cover_names = ['cover', 'front', 'back']
        candidates = [candidate.path for candidate in
                      self.source.get(None, self.settings, [self.dpath])]
        self.assertEqual(candidates, paths)


class CombinedTest(FetchImageHelper, UseThePlugin):
    ASIN = 'xxxx'
    MBID = 'releaseid'
    AMAZON_URL = 'http://images.amazon.com/images/P/{0}.01.LZZZZZZZ.jpg' \
                 .format(ASIN)
    AAO_URL = 'http://www.albumart.org/index_detail.php?asin={0}' \
              .format(ASIN)
    CAA_URL = 'coverartarchive.org/release/{0}/front' \
              .format(MBID)

    def setUp(self):
        super(CombinedTest, self).setUp()
        self.dpath = os.path.join(self.temp_dir, b'arttest')
        os.mkdir(self.dpath)

    def test_main_interface_returns_amazon_art(self):
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        candidate = self.plugin.art_for_album(album, None)
        self.assertIsNotNone(candidate)

    def test_main_interface_returns_none_for_missing_asin_and_path(self):
        album = _common.Bag()
        candidate = self.plugin.art_for_album(album, None)
        self.assertIsNone(candidate)

    def test_main_interface_gives_precedence_to_fs_art(self):
        _common.touch(os.path.join(self.dpath, b'art.jpg'))
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        candidate = self.plugin.art_for_album(album, [self.dpath])
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.path, os.path.join(self.dpath, b'art.jpg'))

    def test_main_interface_falls_back_to_amazon(self):
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        candidate = self.plugin.art_for_album(album, [self.dpath])
        self.assertIsNotNone(candidate)
        self.assertFalse(candidate.path.startswith(self.dpath))

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
        self.mock_response("http://" + self.CAA_URL)
        self.mock_response("https://" + self.CAA_URL)
        album = _common.Bag(mb_albumid=self.MBID, asin=self.ASIN)
        candidate = self.plugin.art_for_album(album, None)
        self.assertIsNotNone(candidate)
        self.assertEqual(len(responses.calls), 1)
        if util.SNI_SUPPORTED:
            url = "https://" + self.CAA_URL
        else:
            url = "http://" + self.CAA_URL
        self.assertEqual(responses.calls[0].request.url, url)

    def test_local_only_does_not_access_network(self):
        album = _common.Bag(mb_albumid=self.MBID, asin=self.ASIN)
        self.plugin.art_for_album(album, None, local_only=True)
        self.assertEqual(len(responses.calls), 0)

    def test_local_only_gets_fs_image(self):
        _common.touch(os.path.join(self.dpath, b'art.jpg'))
        album = _common.Bag(mb_albumid=self.MBID, asin=self.ASIN)
        candidate = self.plugin.art_for_album(album, [self.dpath],
                                              local_only=True)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.path, os.path.join(self.dpath, b'art.jpg'))
        self.assertEqual(len(responses.calls), 0)


class AAOTest(UseThePlugin):
    ASIN = 'xxxx'
    AAO_URL = 'http://www.albumart.org/index_detail.php?asin={0}'.format(ASIN)

    def setUp(self):
        super(AAOTest, self).setUp()
        self.source = fetchart.AlbumArtOrg(logger, self.plugin.config)
        self.settings = Settings()

    @responses.activate
    def run(self, *args, **kwargs):
        super(AAOTest, self).run(*args, **kwargs)

    def mock_response(self, url, body):
        responses.add(responses.GET, url, body=body, content_type='text/html',
                      match_querystring=True)

    def test_aao_scraper_finds_image(self):
        body = """
        <br />
        <a href=\"TARGET_URL\" title=\"View larger image\"
           class=\"thickbox\" style=\"color: #7E9DA2; text-decoration:none;\">
        <img src=\"http://www.albumart.org/images/zoom-icon.jpg\"
       alt=\"View larger image\" width=\"17\" height=\"15\"  border=\"0\"/></a>
        """
        self.mock_response(self.AAO_URL, body)
        album = _common.Bag(asin=self.ASIN)
        candidate = next(self.source.get(album, self.settings, []))
        self.assertEqual(candidate.url, 'TARGET_URL')

    def test_aao_scraper_returns_no_result_when_no_image_present(self):
        self.mock_response(self.AAO_URL, 'blah blah')
        album = _common.Bag(asin=self.ASIN)
        with self.assertRaises(StopIteration):
            next(self.source.get(album, self.settings, []))


class ITunesStoreTest(UseThePlugin):
    def setUp(self):
        super(ITunesStoreTest, self).setUp()
        self.source = fetchart.ITunesStore(logger, self.plugin.config)
        self.settings = Settings()
        self.album = _common.Bag(albumartist="some artist", album="some album")

    @responses.activate
    def run(self, *args, **kwargs):
        super(ITunesStoreTest, self).run(*args, **kwargs)

    def mock_response(self, url, json):
        responses.add(responses.GET, url, body=json,
                      content_type='application/json')

    def test_itunesstore_finds_image(self):
        json = """{
                    "results":
                        [
                            {
                                "artistName": "some artist",
                                "collectionName": "some album",
                                "artworkUrl100": "url_to_the_image"
                            }
                        ]
                  }"""
        self.mock_response(fetchart.ITunesStore.API_URL, json)
        candidate = next(self.source.get(self.album, self.settings, []))
        self.assertEqual(candidate.url, 'url_to_the_image')
        self.assertEqual(candidate.match, fetchart.Candidate.MATCH_EXACT)

    def test_itunesstore_no_result(self):
        json = '{"results": []}'
        self.mock_response(fetchart.ITunesStore.API_URL, json)
        expected = u"got no results"

        with capture_log('beets.test_art') as logs:
            with self.assertRaises(StopIteration):
                next(self.source.get(self.album, self.settings, []))
        self.assertIn(expected, logs[1])

    def test_itunesstore_requestexception(self):
        responses.add(responses.GET, fetchart.ITunesStore.API_URL,
                      json={'error': 'not found'}, status=404)
        expected = u'iTunes search failed: 404 Client Error'

        with capture_log('beets.test_art') as logs:
            with self.assertRaises(StopIteration):
                next(self.source.get(self.album, self.settings, []))
        self.assertIn(expected, logs[1])

    def test_itunesstore_fallback_match(self):
        json = """{
                    "results":
                        [
                            {
                                "collectionName": "some album",
                                "artworkUrl100": "url_to_the_image"
                            }
                        ]
                  }"""
        self.mock_response(fetchart.ITunesStore.API_URL, json)
        candidate = next(self.source.get(self.album, self.settings, []))
        self.assertEqual(candidate.url, 'url_to_the_image')
        self.assertEqual(candidate.match, fetchart.Candidate.MATCH_FALLBACK)

    def test_itunesstore_returns_result_without_artwork(self):
        json = """{
                    "results":
                        [
                            {
                                "artistName": "some artist",
                                "collectionName": "some album"
                            }
                        ]
                  }"""
        self.mock_response(fetchart.ITunesStore.API_URL, json)
        expected = u'Malformed itunes candidate'

        with capture_log('beets.test_art') as logs:
            with self.assertRaises(StopIteration):
                next(self.source.get(self.album, self.settings, []))
        self.assertIn(expected, logs[1])

    def test_itunesstore_returns_no_result_when_error_received(self):
        json = '{"error": {"errors": [{"reason": "some reason"}]}}'
        self.mock_response(fetchart.ITunesStore.API_URL, json)
        expected = u"not found in json. Fields are"

        with capture_log('beets.test_art') as logs:
            with self.assertRaises(StopIteration):
                next(self.source.get(self.album, self.settings, []))
        self.assertIn(expected, logs[1])

    def test_itunesstore_returns_no_result_with_malformed_response(self):
        json = """bla blup"""
        self.mock_response(fetchart.ITunesStore.API_URL, json)
        expected = u"Could not decode json response:"

        with capture_log('beets.test_art') as logs:
            with self.assertRaises(StopIteration):
                next(self.source.get(self.album, self.settings, []))
        self.assertIn(expected, logs[1])


class GoogleImageTest(UseThePlugin):
    def setUp(self):
        super(GoogleImageTest, self).setUp()
        self.source = fetchart.GoogleImages(logger, self.plugin.config)
        self.settings = Settings()

    @responses.activate
    def run(self, *args, **kwargs):
        super(GoogleImageTest, self).run(*args, **kwargs)

    def mock_response(self, url, json):
        responses.add(responses.GET, url, body=json,
                      content_type='application/json')

    def test_google_art_finds_image(self):
        album = _common.Bag(albumartist="some artist", album="some album")
        json = '{"items": [{"link": "url_to_the_image"}]}'
        self.mock_response(fetchart.GoogleImages.URL, json)
        candidate = next(self.source.get(album, self.settings, []))
        self.assertEqual(candidate.url, 'url_to_the_image')

    def test_google_art_returns_no_result_when_error_received(self):
        album = _common.Bag(albumartist="some artist", album="some album")
        json = '{"error": {"errors": [{"reason": "some reason"}]}}'
        self.mock_response(fetchart.GoogleImages.URL, json)
        with self.assertRaises(StopIteration):
            next(self.source.get(album, self.settings, []))

    def test_google_art_returns_no_result_with_malformed_response(self):
        album = _common.Bag(albumartist="some artist", album="some album")
        json = """bla blup"""
        self.mock_response(fetchart.GoogleImages.URL, json)
        with self.assertRaises(StopIteration):
            next(self.source.get(album, self.settings, []))


class FanartTVTest(UseThePlugin):
    RESPONSE_MULTIPLE = u"""{
        "name": "artistname",
        "mbid_id": "artistid",
        "albums": {
            "thereleasegroupid": {
                "albumcover": [
                    {
                        "id": "24",
                        "url": "http://example.com/1.jpg",
                        "likes": "0"
                    },
                    {
                        "id": "42",
                        "url": "http://example.com/2.jpg",
                        "likes": "0"
                    },
                    {
                        "id": "23",
                        "url": "http://example.com/3.jpg",
                        "likes": "0"
                    }
                ],
                "cdart": [
                    {
                        "id": "123",
                        "url": "http://example.com/4.jpg",
                        "likes": "0",
                        "disc": "1",
                        "size": "1000"
                    }
                ]
            }
        }
    }"""
    RESPONSE_NO_ART = u"""{
        "name": "artistname",
        "mbid_id": "artistid",
        "albums": {
            "thereleasegroupid": {
               "cdart": [
                    {
                        "id": "123",
                        "url": "http://example.com/4.jpg",
                        "likes": "0",
                        "disc": "1",
                        "size": "1000"
                    }
                ]
            }
        }
    }"""
    RESPONSE_ERROR = u"""{
        "status": "error",
        "error message": "the error message"
    }"""
    RESPONSE_MALFORMED = u"bla blup"

    def setUp(self):
        super(FanartTVTest, self).setUp()
        self.source = fetchart.FanartTV(logger, self.plugin.config)
        self.settings = Settings()

    @responses.activate
    def run(self, *args, **kwargs):
        super(FanartTVTest, self).run(*args, **kwargs)

    def mock_response(self, url, json):
        responses.add(responses.GET, url, body=json,
                      content_type='application/json')

    def test_fanarttv_finds_image(self):
        album = _common.Bag(mb_releasegroupid=u'thereleasegroupid')
        self.mock_response(fetchart.FanartTV.API_ALBUMS + u'thereleasegroupid',
                           self.RESPONSE_MULTIPLE)
        candidate = next(self.source.get(album, self.settings, []))
        self.assertEqual(candidate.url, 'http://example.com/1.jpg')

    def test_fanarttv_returns_no_result_when_error_received(self):
        album = _common.Bag(mb_releasegroupid=u'thereleasegroupid')
        self.mock_response(fetchart.FanartTV.API_ALBUMS + u'thereleasegroupid',
                           self.RESPONSE_ERROR)
        with self.assertRaises(StopIteration):
            next(self.source.get(album, self.settings, []))

    def test_fanarttv_returns_no_result_with_malformed_response(self):
        album = _common.Bag(mb_releasegroupid=u'thereleasegroupid')
        self.mock_response(fetchart.FanartTV.API_ALBUMS + u'thereleasegroupid',
                           self.RESPONSE_MALFORMED)
        with self.assertRaises(StopIteration):
            next(self.source.get(album, self.settings, []))

    def test_fanarttv_only_other_images(self):
        # The source used to fail when there were images present, but no cover
        album = _common.Bag(mb_releasegroupid=u'thereleasegroupid')
        self.mock_response(fetchart.FanartTV.API_ALBUMS + u'thereleasegroupid',
                           self.RESPONSE_NO_ART)
        with self.assertRaises(StopIteration):
            next(self.source.get(album, self.settings, []))


@_common.slow_test()
class ArtImporterTest(UseThePlugin):
    def setUp(self):
        super(ArtImporterTest, self).setUp()

        # Mock the album art fetcher to always return our test file.
        self.art_file = os.path.join(self.temp_dir, b'tmpcover.jpg')
        _common.touch(self.art_file)
        self.old_afa = self.plugin.art_for_album
        self.afa_response = fetchart.Candidate(logger, path=self.art_file)

        def art_for_album(i, p, local_only=False):
            return self.afa_response

        self.plugin.art_for_album = art_for_album

        # Test library.
        self.libpath = os.path.join(self.temp_dir, b'tmplib.blb')
        self.libdir = os.path.join(self.temp_dir, b'tmplib')
        os.mkdir(self.libdir)
        os.mkdir(os.path.join(self.libdir, b'album'))
        itempath = os.path.join(self.libdir, b'album', b'test.mp3')
        shutil.copyfile(os.path.join(_common.RSRC, b'full.mp3'), itempath)
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
            album=u'some album',
            album_id=u'albumid',
            artist=u'some artist',
            artist_id=u'artistid',
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
                os.path.join(os.path.dirname(self.i.path), b'cover.jpg')
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
        self.plugin.src_removed = True
        self._fetch_art(True)
        self.assertNotExists(self.art_file)

    def test_do_not_delete_original_if_already_in_place(self):
        artdest = os.path.join(os.path.dirname(self.i.path), b'cover.jpg')
        shutil.copyfile(self.art_file, artdest)
        self.afa_response = fetchart.Candidate(logger, path=artdest)
        self._fetch_art(True)

    def test_fetch_art_if_imported_file_deleted(self):
        # See #1126. Test the following scenario:
        #   - Album art imported, `album.artpath` set.
        #   - Imported album art file subsequently deleted (by user or other
        #     program).
        # `fetchart` should import album art again instead of printing the
        # message "<album> has album art".
        self._fetch_art(True)
        util.remove(self.album.artpath)
        self.plugin.batch_fetch_art(self.lib, self.lib.albums(), force=False,
                                    quiet=False)
        self.assertExists(self.album.artpath)


class ArtForAlbumTest(UseThePlugin):
    """ Tests that fetchart.art_for_album respects the size
    configuration (e.g., minwidth, enforce_ratio)
    """

    IMG_225x225 = os.path.join(_common.RSRC, b'abbey.jpg')
    IMG_348x348 = os.path.join(_common.RSRC, b'abbey-different.jpg')
    IMG_500x490 = os.path.join(_common.RSRC, b'abbey-similar.jpg')

    def setUp(self):
        super(ArtForAlbumTest, self).setUp()

        self.old_fs_source_get = fetchart.FileSystem.get

        def fs_source_get(_self, album, settings, paths):
            if paths:
                yield fetchart.Candidate(logger, path=self.image_file)

        fetchart.FileSystem.get = fs_source_get

        self.album = _common.Bag()

    def tearDown(self):
        fetchart.FileSystem.get = self.old_fs_source_get
        super(ArtForAlbumTest, self).tearDown()

    def _assertImageIsValidArt(self, image_file, should_exist):  # noqa
        self.assertExists(image_file)
        self.image_file = image_file

        candidate = self.plugin.art_for_album(self.album, [''], True)

        if should_exist:
            self.assertNotEqual(candidate, None)
            self.assertEqual(candidate.path, self.image_file)
            self.assertExists(candidate.path)
        else:
            self.assertIsNone(candidate)

    def _assertImageResized(self, image_file, should_resize):  # noqa
        self.image_file = image_file
        with patch.object(ArtResizer.shared, 'resize') as mock_resize:
            self.plugin.art_for_album(self.album, [''], True)
            self.assertEqual(mock_resize.called, should_resize)

    def _require_backend(self):
        """Skip the test if the art resizer doesn't have ImageMagick or
        PIL (so comparisons and measurements are unavailable).
        """
        if ArtResizer.shared.method[0] == WEBPROXY:
            self.skipTest(u"ArtResizer has no local imaging backend available")

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

    def test_respect_enforce_ratio_px_above(self):
        self._require_backend()
        self.plugin.enforce_ratio = True
        self.plugin.margin_px = 5
        self._assertImageIsValidArt(self.IMG_500x490, False)

    def test_respect_enforce_ratio_px_below(self):
        self._require_backend()
        self.plugin.enforce_ratio = True
        self.plugin.margin_px = 15
        self._assertImageIsValidArt(self.IMG_500x490, True)

    def test_respect_enforce_ratio_percent_above(self):
        self._require_backend()
        self.plugin.enforce_ratio = True
        self.plugin.margin_percent = (500 - 490) / 500 * 0.5
        self._assertImageIsValidArt(self.IMG_500x490, False)

    def test_respect_enforce_ratio_percent_below(self):
        self._require_backend()
        self.plugin.enforce_ratio = True
        self.plugin.margin_percent = (500 - 490) / 500 * 1.5
        self._assertImageIsValidArt(self.IMG_500x490, True)

    def test_resize_if_necessary(self):
        self._require_backend()
        self.plugin.maxwidth = 300
        self._assertImageResized(self.IMG_225x225, False)
        self._assertImageResized(self.IMG_348x348, True)


class DeprecatedConfigTest(_common.TestCase):
    """While refactoring the plugin, the remote_priority option was deprecated,
    and a new codepath should translate its effect. Check that it actually does
    so.
    """

    # If we subclassed UseThePlugin, the configuration change would either be
    # overwritten by _common.TestCase or be set after constructing the
    # plugin object
    def setUp(self):
        super(DeprecatedConfigTest, self).setUp()
        config['fetchart']['remote_priority'] = True
        self.plugin = fetchart.FetchArtPlugin()

    def test_moves_filesystem_to_end(self):
        self.assertEqual(type(self.plugin.sources[-1]), fetchart.FileSystem)


class EnforceRatioConfigTest(_common.TestCase):
    """Throw some data at the regexes."""

    def _load_with_config(self, values, should_raise):
        if should_raise:
            for v in values:
                config['fetchart']['enforce_ratio'] = v
                with self.assertRaises(confit.ConfigValueError):
                    fetchart.FetchArtPlugin()
        else:
            for v in values:
                config['fetchart']['enforce_ratio'] = v
                fetchart.FetchArtPlugin()

    def test_px(self):
        self._load_with_config(u'0px 4px 12px 123px'.split(), False)
        self._load_with_config(u'00px stuff5px'.split(), True)

    def test_percent(self):
        self._load_with_config(u'0% 0.00% 5.1% 5% 100%'.split(), False)
        self._load_with_config(u'00% 1.234% foo5% 100.1%'.split(), True)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
