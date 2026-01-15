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

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import confuse
import pytest
import responses

from beets import config, importer, logging, util
from beets.autotag import AlbumInfo, AlbumMatch
from beets.test import _common
from beets.test.helper import (
    BeetsTestCase,
    CleanupModulesMixin,
    FetchImageHelper,
    capture_log,
)
from beets.util import syspath
from beets.util.artresizer import ArtResizer
from beetsplug import fetchart

logger = logging.getLogger("beets.test_art")

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from beets.library import Album


class Settings:
    """Used to pass settings to the ArtSources when the plugin isn't fully
    instantiated.
    """

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class DummyRemoteArtSource(fetchart.RemoteArtSource):
    NAME = "Dummy Art Source"
    ID = "dummy"

    def get(
        self,
        album: Album,
        plugin: fetchart.FetchArtPlugin,
        paths: None | Sequence[bytes],
    ) -> Iterator[fetchart.Candidate]:
        return iter(())


class UseThePlugin(CleanupModulesMixin, BeetsTestCase):
    modules = (fetchart.__name__, ArtResizer.__module__)

    def setUp(self):
        super().setUp()
        self.plugin = fetchart.FetchArtPlugin()


class FetchImageTestCase(FetchImageHelper, UseThePlugin):
    pass


class CAAHelper:
    """Helper mixin for mocking requests to the Cover Art Archive."""

    MBID_RELASE = "rid"
    MBID_GROUP = "rgid"

    RELEASE_URL = f"coverartarchive.org/release/{MBID_RELASE}"
    GROUP_URL = f"coverartarchive.org/release-group/{MBID_GROUP}"

    RELEASE_URL = f"https://{RELEASE_URL}"
    GROUP_URL = f"https://{GROUP_URL}"

    RESPONSE_RELEASE = """{
    "images": [
      {
        "approved": false,
        "back": false,
        "comment": "GIF",
        "edit": 12345,
        "front": true,
        "id": 12345,
        "image": "http://coverartarchive.org/release/rid/12345.gif",
        "thumbnails": {
          "1200": "http://coverartarchive.org/release/rid/12345-1200.jpg",
          "250": "http://coverartarchive.org/release/rid/12345-250.jpg",
          "500": "http://coverartarchive.org/release/rid/12345-500.jpg",
          "large": "http://coverartarchive.org/release/rid/12345-500.jpg",
          "small": "http://coverartarchive.org/release/rid/12345-250.jpg"
        },
        "types": [
          "Front"
        ]
      },
      {
        "approved": false,
        "back": false,
        "comment": "",
        "edit": 12345,
        "front": false,
        "id": 12345,
        "image": "http://coverartarchive.org/release/rid/12345.jpg",
        "thumbnails": {
          "1200": "http://coverartarchive.org/release/rid/12345-1200.jpg",
          "250": "http://coverartarchive.org/release/rid/12345-250.jpg",
          "500": "http://coverartarchive.org/release/rid/12345-500.jpg",
          "large": "http://coverartarchive.org/release/rid/12345-500.jpg",
          "small": "http://coverartarchive.org/release/rid/12345-250.jpg"
        },
        "types": [
          "Front"
        ]
      }
    ],
    "release": "https://musicbrainz.org/release/releaseid"
}"""
    RESPONSE_RELEASE_WITHOUT_THUMBNAILS = """{
    "images": [
      {
        "approved": false,
        "back": false,
        "comment": "GIF",
        "edit": 12345,
        "front": true,
        "id": 12345,
        "image": "http://coverartarchive.org/release/rid/12345.gif",
        "types": [
          "Front"
        ]
      },
      {
        "approved": false,
        "back": false,
        "comment": "",
        "edit": 12345,
        "front": false,
        "id": 12345,
        "image": "http://coverartarchive.org/release/rid/12345.jpg",
        "thumbnails": {
            "large": "http://coverartarchive.org/release/rgid/12345-500.jpg",
            "small": "http://coverartarchive.org/release/rgid/12345-250.jpg"
        },
        "types": [
          "Front"
        ]
      }
    ],
    "release": "https://musicbrainz.org/release/releaseid"
}"""
    RESPONSE_GROUP = """{
        "images": [
          {
            "approved": false,
            "back": false,
            "comment": "",
            "edit": 12345,
            "front": true,
            "id": 12345,
            "image": "http://coverartarchive.org/release/releaseid/12345.jpg",
            "thumbnails": {
              "1200": "http://coverartarchive.org/release/rgid/12345-1200.jpg",
              "250": "http://coverartarchive.org/release/rgid/12345-250.jpg",
              "500": "http://coverartarchive.org/release/rgid/12345-500.jpg",
              "large": "http://coverartarchive.org/release/rgid/12345-500.jpg",
              "small": "http://coverartarchive.org/release/rgid/12345-250.jpg"
            },
            "types": [
              "Front"
            ]
          }
        ],
        "release": "https://musicbrainz.org/release/release-id"
    }"""
    RESPONSE_GROUP_WITHOUT_THUMBNAILS = """{
        "images": [
          {
            "approved": false,
            "back": false,
            "comment": "",
            "edit": 12345,
            "front": true,
            "id": 12345,
            "image": "http://coverartarchive.org/release/releaseid/12345.jpg",
            "types": [
              "Front"
            ]
          }
        ],
        "release": "https://musicbrainz.org/release/release-id"
    }"""

    def mock_caa_response(self, url, json):
        responses.add(
            responses.GET, url, body=json, content_type="application/json"
        )


class FetchImageTest(FetchImageTestCase):
    URL = "http://example.com/test.jpg"

    def setUp(self):
        super().setUp()
        self.dpath = os.path.join(self.temp_dir, b"arttest")
        self.source = DummyRemoteArtSource(logger, self.plugin.config)
        self.settings = Settings(maxwidth=0)
        self.candidate = fetchart.Candidate(
            logger, self.source.ID, url=self.URL
        )

    def test_invalid_type_returns_none(self):
        self.mock_response(self.URL, "image/watercolour")
        self.source.fetch_image(self.candidate, self.settings)
        assert self.candidate.path is None

    def test_jpeg_type_returns_path(self):
        self.mock_response(self.URL, "image/jpeg")
        self.source.fetch_image(self.candidate, self.settings)
        assert self.candidate.path is not None

    def test_extension_set_by_content_type(self):
        self.mock_response(self.URL, "image/png")
        self.source.fetch_image(self.candidate, self.settings)
        assert os.path.splitext(self.candidate.path)[1] == b".png"
        assert Path(os.fsdecode(self.candidate.path)).exists()

    def test_does_not_rely_on_server_content_type(self):
        self.mock_response(self.URL, "image/jpeg", "image/png")
        self.source.fetch_image(self.candidate, self.settings)
        assert os.path.splitext(self.candidate.path)[1] == b".png"
        assert Path(os.fsdecode(self.candidate.path)).exists()


class FSArtTest(UseThePlugin):
    def setUp(self):
        super().setUp()
        self.dpath = os.path.join(self.temp_dir, b"arttest")
        os.mkdir(syspath(self.dpath))

        self.source = fetchart.FileSystem(logger, self.plugin.config)
        self.settings = Settings(
            cautious=False, cover_names=("art",), fallback=None
        )

    def test_finds_jpg_in_directory(self):
        _common.touch(os.path.join(self.dpath, b"a.jpg"))
        candidate = next(self.source.get(None, self.settings, [self.dpath]))
        assert candidate.path == os.path.join(self.dpath, b"a.jpg")

    def test_appropriately_named_file_takes_precedence(self):
        _common.touch(os.path.join(self.dpath, b"a.jpg"))
        _common.touch(os.path.join(self.dpath, b"art.jpg"))
        candidate = next(self.source.get(None, self.settings, [self.dpath]))
        assert candidate.path == os.path.join(self.dpath, b"art.jpg")

    def test_non_image_file_not_identified(self):
        _common.touch(os.path.join(self.dpath, b"a.txt"))
        with pytest.raises(StopIteration):
            next(self.source.get(None, self.settings, [self.dpath]))

    def test_cautious_skips_fallback(self):
        _common.touch(os.path.join(self.dpath, b"a.jpg"))
        self.settings.cautious = True
        with pytest.raises(StopIteration):
            next(self.source.get(None, self.settings, [self.dpath]))

    def test_configured_fallback_is_used(self):
        fallback = os.path.join(self.temp_dir, b"a.jpg")
        _common.touch(fallback)
        self.settings.fallback = fallback
        candidate = next(self.source.get(None, self.settings, [self.dpath]))
        assert candidate.path == fallback

    def test_empty_dir(self):
        with pytest.raises(StopIteration):
            next(self.source.get(None, self.settings, [self.dpath]))

    def test_precedence_amongst_correct_files(self):
        images = [b"front-cover.jpg", b"front.jpg", b"back.jpg"]
        paths = [os.path.join(self.dpath, i) for i in images]
        for p in paths:
            _common.touch(p)
        self.settings.cover_names = ["cover", "front", "back"]
        candidates = [
            candidate.path
            for candidate in self.source.get(None, self.settings, [self.dpath])
        ]
        assert candidates == paths


class CombinedTest(FetchImageTestCase, CAAHelper):
    ASIN = "xxxx"
    MBID = "releaseid"
    AMAZON_URL = f"https://images.amazon.com/images/P/{ASIN}.01.LZZZZZZZ.jpg"
    AAO_URL = f"https://www.albumart.org/index_detail.php?asin={ASIN}"

    def setUp(self):
        super().setUp()
        self.dpath = os.path.join(self.temp_dir, b"arttest")
        os.mkdir(syspath(self.dpath))

    def test_main_interface_returns_amazon_art(self):
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        candidate = self.plugin.art_for_album(album, None)
        assert candidate is not None

    def test_main_interface_returns_none_for_missing_asin_and_path(self):
        album = _common.Bag()
        candidate = self.plugin.art_for_album(album, None)
        assert candidate is None

    def test_main_interface_gives_precedence_to_fs_art(self):
        _common.touch(os.path.join(self.dpath, b"art.jpg"))
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        candidate = self.plugin.art_for_album(album, [self.dpath])
        assert candidate is not None
        assert candidate.path == os.path.join(self.dpath, b"art.jpg")

    def test_main_interface_falls_back_to_amazon(self):
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        candidate = self.plugin.art_for_album(album, [self.dpath])
        assert candidate is not None
        assert not candidate.path.startswith(self.dpath)

    def test_main_interface_tries_amazon_before_aao(self):
        self.mock_response(self.AMAZON_URL)
        album = _common.Bag(asin=self.ASIN)
        self.plugin.art_for_album(album, [self.dpath])
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == self.AMAZON_URL

    def test_main_interface_falls_back_to_aao(self):
        self.mock_response(self.AMAZON_URL, content_type="text/html")
        album = _common.Bag(asin=self.ASIN)
        self.plugin.art_for_album(album, [self.dpath])
        assert responses.calls[-1].request.url == self.AAO_URL

    def test_main_interface_uses_caa_when_mbid_available(self):
        self.mock_caa_response(self.RELEASE_URL, self.RESPONSE_RELEASE)
        self.mock_caa_response(self.GROUP_URL, self.RESPONSE_GROUP)
        self.mock_response(
            "http://coverartarchive.org/release/rid/12345.gif",
            content_type="image/gif",
        )
        self.mock_response(
            "http://coverartarchive.org/release/rid/12345.jpg",
            content_type="image/jpeg",
        )
        album = _common.Bag(
            mb_albumid=self.MBID_RELASE,
            mb_releasegroupid=self.MBID_GROUP,
            asin=self.ASIN,
        )
        candidate = self.plugin.art_for_album(album, None)
        assert candidate is not None
        assert len(responses.calls) == 3
        assert responses.calls[0].request.url == self.RELEASE_URL

    def test_local_only_does_not_access_network(self):
        album = _common.Bag(mb_albumid=self.MBID, asin=self.ASIN)
        self.plugin.art_for_album(album, None, local_only=True)
        assert len(responses.calls) == 0

    def test_local_only_gets_fs_image(self):
        _common.touch(os.path.join(self.dpath, b"art.jpg"))
        album = _common.Bag(mb_albumid=self.MBID, asin=self.ASIN)
        candidate = self.plugin.art_for_album(
            album, [self.dpath], local_only=True
        )
        assert candidate is not None
        assert candidate.path == os.path.join(self.dpath, b"art.jpg")
        assert len(responses.calls) == 0


class AAOTest(UseThePlugin):
    ASIN = "xxxx"
    AAO_URL = f"https://www.albumart.org/index_detail.php?asin={ASIN}"

    def setUp(self):
        super().setUp()
        self.source = fetchart.AlbumArtOrg(logger, self.plugin.config)
        self.settings = Settings()

    @responses.activate
    def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def mock_response(self, url, body):
        responses.add(responses.GET, url, body=body, content_type="text/html")

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
        assert candidate.url == "TARGET_URL"

    def test_aao_scraper_returns_no_result_when_no_image_present(self):
        self.mock_response(self.AAO_URL, "blah blah")
        album = _common.Bag(asin=self.ASIN)
        with pytest.raises(StopIteration):
            next(self.source.get(album, self.settings, []))


class ITunesStoreTest(UseThePlugin):
    def setUp(self):
        super().setUp()
        self.source = fetchart.ITunesStore(logger, self.plugin.config)
        self.settings = Settings()
        self.album = _common.Bag(albumartist="some artist", album="some album")

    @responses.activate
    def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def mock_response(self, url, json):
        responses.add(
            responses.GET, url, body=json, content_type="application/json"
        )

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
        assert candidate.url == "url_to_the_image"
        assert candidate.match == fetchart.MetadataMatch.EXACT

    def test_itunesstore_no_result(self):
        json = '{"results": []}'
        self.mock_response(fetchart.ITunesStore.API_URL, json)
        expected = "got no results"

        with capture_log("beets.test_art") as logs:
            with pytest.raises(StopIteration):
                next(self.source.get(self.album, self.settings, []))
        assert expected in logs[1]

    def test_itunesstore_requestexception(self):
        responses.add(
            responses.GET,
            fetchart.ITunesStore.API_URL,
            json={"error": "not found"},
            status=404,
        )
        expected = "iTunes search failed: 404 Client Error"

        with capture_log("beets.test_art") as logs:
            with pytest.raises(StopIteration):
                next(self.source.get(self.album, self.settings, []))
        assert expected in logs[1]

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
        assert candidate.url == "url_to_the_image"
        assert candidate.match == fetchart.MetadataMatch.FALLBACK

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
        expected = "Malformed itunes candidate"

        with capture_log("beets.test_art") as logs:
            with pytest.raises(StopIteration):
                next(self.source.get(self.album, self.settings, []))
        assert expected in logs[1]

    def test_itunesstore_returns_no_result_when_error_received(self):
        json = '{"error": {"errors": [{"reason": "some reason"}]}}'
        self.mock_response(fetchart.ITunesStore.API_URL, json)
        expected = "not found in json. Fields are"

        with capture_log("beets.test_art") as logs:
            with pytest.raises(StopIteration):
                next(self.source.get(self.album, self.settings, []))
        assert expected in logs[1]

    def test_itunesstore_returns_no_result_with_malformed_response(self):
        json = """bla blup"""
        self.mock_response(fetchart.ITunesStore.API_URL, json)
        expected = "Could not decode json response:"

        with capture_log("beets.test_art") as logs:
            with pytest.raises(StopIteration):
                next(self.source.get(self.album, self.settings, []))
        assert expected in logs[1]


class GoogleImageTest(UseThePlugin):
    def setUp(self):
        super().setUp()
        self.source = fetchart.GoogleImages(logger, self.plugin.config)
        self.settings = Settings()

    @responses.activate
    def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def mock_response(self, url, json):
        responses.add(
            responses.GET, url, body=json, content_type="application/json"
        )

    def test_google_art_finds_image(self):
        album = _common.Bag(albumartist="some artist", album="some album")
        json = '{"items": [{"link": "url_to_the_image"}]}'
        self.mock_response(fetchart.GoogleImages.URL, json)
        candidate = next(self.source.get(album, self.settings, []))
        assert candidate.url == "url_to_the_image"

    def test_google_art_returns_no_result_when_error_received(self):
        album = _common.Bag(albumartist="some artist", album="some album")
        json = '{"error": {"errors": [{"reason": "some reason"}]}}'
        self.mock_response(fetchart.GoogleImages.URL, json)
        with pytest.raises(StopIteration):
            next(self.source.get(album, self.settings, []))

    def test_google_art_returns_no_result_with_malformed_response(self):
        album = _common.Bag(albumartist="some artist", album="some album")
        json = """bla blup"""
        self.mock_response(fetchart.GoogleImages.URL, json)
        with pytest.raises(StopIteration):
            next(self.source.get(album, self.settings, []))


class CoverArtArchiveTest(UseThePlugin, CAAHelper):
    def setUp(self):
        super().setUp()
        self.source = fetchart.CoverArtArchive(logger, self.plugin.config)
        self.settings = Settings(maxwidth=0)

    @responses.activate
    def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def test_caa_finds_image(self):
        album = _common.Bag(
            mb_albumid=self.MBID_RELASE, mb_releasegroupid=self.MBID_GROUP
        )
        self.mock_caa_response(self.RELEASE_URL, self.RESPONSE_RELEASE)
        self.mock_caa_response(self.GROUP_URL, self.RESPONSE_GROUP)
        candidates = list(self.source.get(album, self.settings, []))
        assert len(candidates) == 3
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == self.RELEASE_URL

    def test_fetchart_uses_caa_pre_sized_maxwidth_thumbs(self):
        # CAA provides pre-sized thumbnails of width 250px, 500px, and 1200px
        # We only test with one of them here
        maxwidth = 1200
        self.settings = Settings(maxwidth=maxwidth)

        album = _common.Bag(
            mb_albumid=self.MBID_RELASE, mb_releasegroupid=self.MBID_GROUP
        )
        self.mock_caa_response(self.RELEASE_URL, self.RESPONSE_RELEASE)
        self.mock_caa_response(self.GROUP_URL, self.RESPONSE_GROUP)
        candidates = list(self.source.get(album, self.settings, []))
        assert len(candidates) == 3
        for candidate in candidates:
            assert f"-{maxwidth}.jpg" in candidate.url

    def test_caa_finds_image_if_maxwidth_is_set_and_thumbnails_is_empty(self):
        # CAA provides pre-sized thumbnails of width 250px, 500px, and 1200px
        # We only test with one of them here
        maxwidth = 1200
        self.settings = Settings(maxwidth=maxwidth)

        album = _common.Bag(
            mb_albumid=self.MBID_RELASE, mb_releasegroupid=self.MBID_GROUP
        )
        self.mock_caa_response(
            self.RELEASE_URL, self.RESPONSE_RELEASE_WITHOUT_THUMBNAILS
        )
        self.mock_caa_response(
            self.GROUP_URL,
            self.RESPONSE_GROUP_WITHOUT_THUMBNAILS,
        )
        candidates = list(self.source.get(album, self.settings, []))
        assert len(candidates) == 3
        for candidate in candidates:
            assert f"-{maxwidth}.jpg" not in candidate.url


class FanartTVTest(UseThePlugin):
    RESPONSE_MULTIPLE = """{
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
    RESPONSE_NO_ART = """{
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
    RESPONSE_ERROR = """{
        "status": "error",
        "error message": "the error message"
    }"""
    RESPONSE_MALFORMED = "bla blup"

    def setUp(self):
        super().setUp()
        self.source = fetchart.FanartTV(logger, self.plugin.config)
        self.settings = Settings()

    @responses.activate
    def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def mock_response(self, url, json):
        responses.add(
            responses.GET, url, body=json, content_type="application/json"
        )

    def test_fanarttv_finds_image(self):
        album = _common.Bag(mb_releasegroupid="thereleasegroupid")
        self.mock_response(
            f"{fetchart.FanartTV.API_ALBUMS}thereleasegroupid",
            self.RESPONSE_MULTIPLE,
        )
        candidate = next(self.source.get(album, self.settings, []))
        assert candidate.url == "http://example.com/1.jpg"

    def test_fanarttv_returns_no_result_when_error_received(self):
        album = _common.Bag(mb_releasegroupid="thereleasegroupid")
        self.mock_response(
            f"{fetchart.FanartTV.API_ALBUMS}thereleasegroupid",
            self.RESPONSE_ERROR,
        )
        with pytest.raises(StopIteration):
            next(self.source.get(album, self.settings, []))

    def test_fanarttv_returns_no_result_with_malformed_response(self):
        album = _common.Bag(mb_releasegroupid="thereleasegroupid")
        self.mock_response(
            f"{fetchart.FanartTV.API_ALBUMS}thereleasegroupid",
            self.RESPONSE_MALFORMED,
        )
        with pytest.raises(StopIteration):
            next(self.source.get(album, self.settings, []))

    def test_fanarttv_only_other_images(self):
        # The source used to fail when there were images present, but no cover
        album = _common.Bag(mb_releasegroupid="thereleasegroupid")
        self.mock_response(
            f"{fetchart.FanartTV.API_ALBUMS}thereleasegroupid",
            self.RESPONSE_NO_ART,
        )
        with pytest.raises(StopIteration):
            next(self.source.get(album, self.settings, []))


@_common.slow_test()
class ArtImporterTest(UseThePlugin):
    def setUp(self):
        super().setUp()

        # Mock the album art fetcher to always return our test file.
        self.art_file = self.temp_dir_path / "tmpcover.jpg"
        self.art_file.touch()
        self.old_afa = self.plugin.art_for_album
        self.afa_response = fetchart.Candidate(
            logger,
            source_name="test",
            path=self.art_file,
        )

        def art_for_album(i, p, local_only=False):
            return self.afa_response

        self.plugin.art_for_album = art_for_album

        # Test library.
        os.mkdir(syspath(os.path.join(self.libdir, b"album")))
        itempath = os.path.join(self.libdir, b"album", b"test.mp3")
        shutil.copyfile(
            syspath(os.path.join(_common.RSRC, b"full.mp3")),
            syspath(itempath),
        )
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
            album="some album",
            album_id="albumid",
            artist="some artist",
            artist_id="artistid",
            tracks=[],
        )
        self.task.set_choice(AlbumMatch(0, info, {}, set(), set()))

    def tearDown(self):
        super().tearDown()
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

        artpath = self.lib.albums()[0].art_filepath
        if should_exist:
            assert artpath == self.i.filepath.parent / "cover.jpg"
            assert artpath.exists()
        else:
            assert artpath is None
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
        assert self.art_file.exists()

    def test_delete_original_file(self):
        prev_move = config["import"]["move"].get()
        try:
            config["import"]["move"] = True
            self._fetch_art(True)
            assert not self.art_file.exists()
        finally:
            config["import"]["move"] = prev_move

    def test_do_not_delete_original_if_already_in_place(self):
        artdest = os.path.join(os.path.dirname(self.i.path), b"cover.jpg")
        shutil.copyfile(self.art_file, syspath(artdest))
        self.afa_response = fetchart.Candidate(
            logger,
            source_name="test",
            path=artdest,
        )
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
        self.plugin.batch_fetch_art(
            self.lib, self.lib.albums(), force=False, quiet=False
        )
        assert self.album.art_filepath.exists()


class AlbumArtOperationTestCase(UseThePlugin):
    """Base test case for album art operations.

    Provides common setup for testing album art processing operations by setting
    up a mock filesystem source that returns a predefined test image.
    """

    IMAGE_PATH = os.path.join(_common.RSRC, b"abbey-similar.jpg")
    IMAGE_FILESIZE = os.stat(util.syspath(IMAGE_PATH)).st_size
    IMAGE_WIDTH = 500
    IMAGE_HEIGHT = 490
    IMAGE_WIDTH_HEIGHT_DIFF = IMAGE_WIDTH - IMAGE_HEIGHT

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def fs_source_get(_self, album, settings, paths):
            if paths:
                yield fetchart.Candidate(
                    logger, source_name=_self.ID, path=cls.IMAGE_PATH
                )

        patch("beetsplug.fetchart.FileSystem.get", fs_source_get).start()
        cls.addClassCleanup(patch.stopall)

    def get_album_art(self):
        return self.plugin.art_for_album(_common.Bag(), [""], True)


class AlbumArtOperationConfigurationTest(AlbumArtOperationTestCase):
    """Check that scale & filesize configuration is respected.

    Depending on `minwidth`, `enforce_ratio`, `margin_px`, and `margin_percent`
    configuration the plugin should or should not return an art candidate.
    """

    def test_minwidth(self):
        self.plugin.minwidth = self.IMAGE_WIDTH / 2
        assert self.get_album_art()

        self.plugin.minwidth = self.IMAGE_WIDTH * 2
        assert not self.get_album_art()

    def test_enforce_ratio(self):
        self.plugin.enforce_ratio = True
        assert not self.get_album_art()

        self.plugin.enforce_ratio = False
        assert self.get_album_art()

    def test_enforce_ratio_with_px_margin(self):
        self.plugin.enforce_ratio = True

        self.plugin.margin_px = self.IMAGE_WIDTH_HEIGHT_DIFF * 0.5
        assert not self.get_album_art()

        self.plugin.margin_px = self.IMAGE_WIDTH_HEIGHT_DIFF * 1.5
        assert self.get_album_art()

    def test_enforce_ratio_with_percent_margin(self):
        self.plugin.enforce_ratio = True
        diff_by_width = self.IMAGE_WIDTH_HEIGHT_DIFF / self.IMAGE_WIDTH

        self.plugin.margin_percent = diff_by_width * 0.5
        assert not self.get_album_art()

        self.plugin.margin_percent = diff_by_width * 1.5
        assert self.get_album_art()


class AlbumArtPerformOperationTest(AlbumArtOperationTestCase):
    """Test that the art is resized and deinterlaced if necessary."""

    def setUp(self):
        super().setUp()
        self.resizer_mock = patch.object(
            ArtResizer.shared, "resize", return_value=self.IMAGE_PATH
        ).start()
        self.deinterlacer_mock = patch.object(
            ArtResizer.shared, "deinterlace", return_value=self.IMAGE_PATH
        ).start()

    def test_resize(self):
        self.plugin.maxwidth = self.IMAGE_WIDTH / 2
        assert self.get_album_art()
        assert self.resizer_mock.called

    def test_file_resized(self):
        self.plugin.max_filesize = self.IMAGE_FILESIZE // 2
        assert self.get_album_art()
        assert self.resizer_mock.called

    def test_file_not_resized(self):
        self.plugin.max_filesize = self.IMAGE_FILESIZE
        assert self.get_album_art()
        assert not self.resizer_mock.called

    def test_file_resized_but_not_scaled(self):
        self.plugin.maxwidth = self.IMAGE_WIDTH * 2
        self.plugin.max_filesize = self.IMAGE_FILESIZE // 2
        assert self.get_album_art()
        assert self.resizer_mock.called

    def test_file_resized_and_scaled(self):
        self.plugin.maxwidth = self.IMAGE_WIDTH / 2
        self.plugin.max_filesize = self.IMAGE_FILESIZE // 2
        assert self.get_album_art()
        assert self.resizer_mock.called

    def test_deinterlaced(self):
        self.plugin.deinterlace = True
        assert self.get_album_art()
        assert self.deinterlacer_mock.called

    def test_not_deinterlaced(self):
        self.plugin.deinterlace = False
        assert self.get_album_art()
        assert not self.deinterlacer_mock.called

    def test_deinterlaced_and_resized(self):
        self.plugin.maxwidth = self.IMAGE_WIDTH / 2
        self.plugin.deinterlace = True
        assert self.get_album_art()
        assert self.deinterlacer_mock.called
        assert self.resizer_mock.called


class DeprecatedConfigTest(unittest.TestCase):
    """While refactoring the plugin, the remote_priority option was deprecated,
    and a new codepath should translate its effect. Check that it actually does
    so.
    """

    # If we subclassed UseThePlugin, the configuration change would either be
    # overwritten by BeetsTestCase or be set after constructing the
    # plugin object
    def setUp(self):
        super().setUp()
        config["fetchart"]["remote_priority"] = True
        self.plugin = fetchart.FetchArtPlugin()

    def test_moves_filesystem_to_end(self):
        assert isinstance(self.plugin.sources[-1], fetchart.FileSystem)


class EnforceRatioConfigTest(unittest.TestCase):
    """Throw some data at the regexes."""

    def _load_with_config(self, values, should_raise):
        if should_raise:
            for v in values:
                config["fetchart"]["enforce_ratio"] = v
                with pytest.raises(confuse.ConfigValueError):
                    fetchart.FetchArtPlugin()
        else:
            for v in values:
                config["fetchart"]["enforce_ratio"] = v
                fetchart.FetchArtPlugin()

    def test_px(self):
        self._load_with_config("0px 4px 12px 123px".split(), False)
        self._load_with_config("00px stuff5px".split(), True)

    def test_percent(self):
        self._load_with_config("0% 0.00% 5.1% 5% 100%".split(), False)
        self._load_with_config("00% 1.234% foo5% 100.1%".split(), True)
