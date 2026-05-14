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
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import confuse
import pytest
import responses

from beets import config, importer, logging, util
from beets.autotag.distance import Distance
from beets.autotag.hooks import AlbumInfo, AlbumMatch
from beets.library import Album
from beets.test import _common
from beets.test.helper import FetchImageHelper, TestHelper
from beets.util import clean_module_tempdir, syspath
from beets.util.artresizer import ArtResizer
from beetsplug import fetchart

logger = logging.getLogger("beets.test_art")


if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from unittest.mock import MagicMock

    from beets.test.helper import ImageResponseMocker


class Settings(fetchart.FetchArtPlugin):
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


class PytestTestHelper(TestHelper):
    """Same as the BeetsTestCase unittest setup but for pytest."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.setup_beets()
        try:
            yield
        finally:
            self.teardown_beets()


class UseThePlugin(PytestTestHelper):
    modules = (fetchart.__name__, ArtResizer.__module__)

    @pytest.fixture(autouse=True)
    def setup_plugin(self, setup):
        self.plugin = fetchart.FetchArtPlugin()

    @pytest.fixture(autouse=True, scope="class")
    def cleanup(self):
        try:
            yield
        finally:
            for module in self.modules:
                clean_module_tempdir(module)


class CAAData:
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
            "types": ["Front"]
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
            "types": ["Front"]
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
            "types": ["Front"]
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
            "types": ["Front"]
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
            "types": ["Front"]
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
            "types": ["Front"]
          }
        ],
        "release": "https://musicbrainz.org/release/release-id"
    }"""


class TestFetchImage(UseThePlugin, FetchImageHelper):
    URL: str = "http://example.com/test.jpg"

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(maxwidth=0)

    @pytest.fixture
    def source(self) -> DummyRemoteArtSource:
        return DummyRemoteArtSource(logger, self.plugin.config)

    @pytest.fixture
    def candidate(self, source: DummyRemoteArtSource) -> fetchart.Candidate:
        return fetchart.Candidate(logger, source.ID, url=self.URL)

    def test_invalid_type_returns_none(
        self,
        source: DummyRemoteArtSource,
        candidate: fetchart.Candidate,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ) -> None:
        image_response_mocker.add(self.URL, content_type="image/watercolour")
        source.fetch_image(candidate, settings)
        assert candidate.path is None

    def test_jpeg_type_returns_path(
        self,
        source: DummyRemoteArtSource,
        candidate: fetchart.Candidate,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ) -> None:
        image_response_mocker.add(self.URL, content_type="image/jpeg")
        source.fetch_image(candidate, settings)
        assert candidate.path is not None

    def test_extension_set_by_content_type(
        self,
        source: DummyRemoteArtSource,
        candidate: fetchart.Candidate,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ) -> None:
        image_response_mocker.add(self.URL, content_type="image/png")
        source.fetch_image(candidate, settings)
        assert candidate.path is not None
        assert os.path.splitext(candidate.path)[1] == b".png"
        assert Path(os.fsdecode(candidate.path)).exists()

    def test_does_not_rely_on_server_content_type(
        self,
        source: DummyRemoteArtSource,
        candidate: fetchart.Candidate,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ) -> None:
        image_response_mocker.add(
            self.URL, content_type="image/jpeg", file_type="image/png"
        )
        source.fetch_image(candidate, settings)
        assert candidate.path is not None
        assert os.path.splitext(candidate.path)[1] == b".png"
        assert Path(os.fsdecode(candidate.path)).exists()


class TestFSArt(UseThePlugin):
    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(cautious=False, cover_names=("art",), fallback=None)

    @pytest.fixture
    def dpath(self) -> bytes:
        dpath = os.path.join(self.temp_dir, b"arttest")
        os.mkdir(syspath(dpath))
        return dpath

    @pytest.fixture
    def source(self) -> fetchart.FileSystem:
        return fetchart.FileSystem(logger, self.plugin.config)

    def test_finds_jpg_in_directory(
        self,
        source: fetchart.FileSystem,
        dpath: bytes,
        settings: Settings,
    ) -> None:
        _common.touch(os.path.join(dpath, b"a.jpg"))
        candidate = next(source.get(Album(), settings, [dpath]))
        assert candidate.path == os.path.join(dpath, b"a.jpg")

    def test_appropriately_named_file_takes_precedence(
        self,
        source: fetchart.FileSystem,
        dpath: bytes,
        settings: Settings,
    ) -> None:
        _common.touch(os.path.join(dpath, b"a.jpg"))
        _common.touch(os.path.join(dpath, b"art.jpg"))
        candidate = next(source.get(Album(), settings, [dpath]))
        assert candidate.path == os.path.join(dpath, b"art.jpg")

    def test_non_image_file_not_identified(
        self,
        source: fetchart.FileSystem,
        dpath: bytes,
        settings: Settings,
    ) -> None:
        _common.touch(os.path.join(dpath, b"a.txt"))
        with pytest.raises(StopIteration):
            next(source.get(Album(), settings, [dpath]))

    def test_cautious_skips_fallback(
        self,
        source: fetchart.FileSystem,
        dpath: bytes,
        settings: Settings,
    ) -> None:
        _common.touch(os.path.join(dpath, b"a.jpg"))
        settings.cautious = True
        with pytest.raises(StopIteration):
            next(source.get(Album(), settings, [dpath]))

    def test_configured_fallback_is_used(
        self,
        source: fetchart.FileSystem,
        dpath: bytes,
        settings: Settings,
    ) -> None:
        fallback = os.path.join(self.temp_dir, b"a.jpg")
        _common.touch(fallback)
        settings.fallback = fallback  # type: ignore
        candidate = next(source.get(Album(), settings, [dpath]))
        assert candidate.path == fallback

    def test_empty_dir(
        self,
        source: fetchart.FileSystem,
        dpath: bytes,
        settings: Settings,
    ) -> None:
        with pytest.raises(StopIteration):
            next(source.get(Album(), settings, [dpath]))

    def test_precedence_amongst_correct_files(
        self,
        source: fetchart.FileSystem,
        dpath: bytes,
        settings: Settings,
    ) -> None:
        images = [b"front-cover.jpg", b"front.jpg", b"back.jpg"]
        paths = [os.path.join(dpath, i) for i in images]
        for p in paths:
            _common.touch(p)
        settings.cover_names = [b"cover", b"front", b"back"]
        candidates = [
            candidate.path
            for candidate in source.get(Album(), settings, [dpath])
        ]
        assert candidates == paths

    @patch("os.path.samefile")
    def test_is_candidate_fallback_os_error(
        self,
        mock_samefile,
        source: fetchart.FileSystem,
    ) -> None:
        mock_samefile.side_effect = OSError("os error")
        fallback = os.path.join(self.temp_dir, b"a.jpg")
        self.plugin.fallback = str(fallback)
        candidate = fetchart.Candidate(logger, source.ID, fallback)
        result = self.plugin._is_candidate_fallback(candidate)
        mock_samefile.assert_called_once()
        assert not result


class TestCombined(UseThePlugin, FetchImageHelper, CAAData):
    ASIN = "xxxx"
    MBID = "releaseid"
    AMAZON_URL = f"https://images.amazon.com/images/P/{ASIN}.01.LZZZZZZZ.jpg"
    AAO_URL = f"https://www.albumart.org/index_detail.php?asin={ASIN}"

    @pytest.fixture
    def dpath(self):
        dpath = os.path.join(self.temp_dir, b"arttest")
        os.mkdir(syspath(dpath))
        return dpath

    def test_main_interface_returns_amazon_art(
        self,
        image_response_mocker: ImageResponseMocker,
    ):
        image_response_mocker.add(self.AMAZON_URL)
        album = Album(asin=self.ASIN)
        candidate = self.plugin.art_for_album(album, None)
        assert candidate is not None

    def test_main_interface_returns_none_for_missing_asin_and_path(self):
        album = Album()
        candidate = self.plugin.art_for_album(album, None)
        assert candidate is None

    def test_main_interface_gives_precedence_to_fs_art(
        self,
        dpath: bytes,
        image_response_mocker: ImageResponseMocker,
    ):
        _common.touch(os.path.join(dpath, b"art.jpg"))
        image_response_mocker.add(self.AMAZON_URL)
        album = Album(asin=self.ASIN)
        candidate = self.plugin.art_for_album(album, [dpath])
        assert candidate is not None
        assert candidate.path == os.path.join(dpath, b"art.jpg")

    def test_main_interface_falls_back_to_amazon(
        self,
        dpath: bytes,
        image_response_mocker: ImageResponseMocker,
    ):
        image_response_mocker.add(self.AMAZON_URL)
        album = Album(asin=self.ASIN)
        candidate = self.plugin.art_for_album(album, [dpath])
        assert candidate is not None
        assert not candidate.path.startswith(dpath)

    def test_main_interface_tries_amazon_before_aao(
        self,
        dpath: bytes,
        image_response_mocker: ImageResponseMocker,
    ):
        image_response_mocker.add(self.AMAZON_URL)
        album = Album(asin=self.ASIN)
        self.plugin.art_for_album(album, [dpath])
        assert len(image_response_mocker.responses_mock.calls) == 1
        assert (
            image_response_mocker.responses_mock.calls[0].request.url
            == self.AMAZON_URL
        )

    def test_main_interface_falls_back_to_aao(
        self,
        dpath: bytes,
        image_response_mocker: ImageResponseMocker,
    ):
        image_response_mocker.add(self.AMAZON_URL, content_type="text/html")
        album = Album(asin=self.ASIN)
        self.plugin.art_for_album(album, [dpath])
        assert (
            image_response_mocker.responses_mock.calls[-1].request.url
            == self.AAO_URL
        )

    def test_main_interface_uses_caa_when_mbid_available(
        self,
        image_response_mocker: ImageResponseMocker,
    ):
        image_response_mocker.add(self.RELEASE_URL, body=self.RESPONSE_RELEASE)
        image_response_mocker.add(self.GROUP_URL, body=self.RESPONSE_GROUP)
        image_response_mocker.add(
            "http://coverartarchive.org/release/rid/12345.gif",
            content_type="image/gif",
        )
        image_response_mocker.add(
            "http://coverartarchive.org/release/rid/12345.jpg",
            content_type="image/jpeg",
        )
        album = Album(
            mb_albumid=self.MBID_RELASE,
            mb_releasegroupid=self.MBID_GROUP,
            asin=self.ASIN,
        )
        candidate = self.plugin.art_for_album(album, None)
        assert candidate is not None
        assert len(image_response_mocker.responses_mock.calls) == 3
        assert (
            image_response_mocker.responses_mock.calls[0].request.url
            == self.RELEASE_URL
        )

    def test_local_only_does_not_access_network(
        self,
        image_response_mocker: ImageResponseMocker,
    ):
        album = Album(mb_albumid=self.MBID, asin=self.ASIN)
        self.plugin.art_for_album(album, None, local_only=True)
        assert len(image_response_mocker.responses_mock.calls) == 0

    def test_local_only_gets_fs_image(
        self,
        dpath: bytes,
        image_response_mocker: ImageResponseMocker,
    ):
        _common.touch(os.path.join(dpath, b"art.jpg"))
        album = Album(mb_albumid=self.MBID, asin=self.ASIN)
        candidate = self.plugin.art_for_album(album, [dpath], local_only=True)
        assert candidate is not None
        assert candidate.path == os.path.join(dpath, b"art.jpg")
        assert len(image_response_mocker.responses_mock.calls) == 0


class TestAAO(UseThePlugin, FetchImageHelper):
    ASIN: str = "xxxx"
    AAO_URL: str = f"https://www.albumart.org/index_detail.php?asin={ASIN}"

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings()

    @pytest.fixture
    def source(self) -> fetchart.AlbumArtOrg:
        return fetchart.AlbumArtOrg(logger, self.plugin.config)

    def test_aao_scraper_finds_image(
        self,
        source: fetchart.AlbumArtOrg,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ) -> None:
        body = """
        <br />
        <a href="TARGET_URL" title="View larger image"
           class="thickbox" style="color: #7E9DA2; text-decoration:none;">
        <img src="http://www.albumart.org/images/zoom-icon.jpg"
             alt="View larger image" width="17" height="15" border="0"/></a>
        """
        image_response_mocker.add(
            self.AAO_URL, body=body, content_type="text/html"
        )
        album = Album(asin=self.ASIN)
        candidate = next(source.get(album, settings, []))
        assert candidate.url == "TARGET_URL"

    def test_aao_scraper_returns_no_result_when_no_image_present(
        self,
        source: fetchart.AlbumArtOrg,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ) -> None:
        image_response_mocker.add(
            self.AAO_URL, body="blah blah", content_type="text/html"
        )
        album = Album(asin=self.ASIN)
        with pytest.raises(StopIteration):
            next(source.get(album, settings, []))


class TestITunesStore(UseThePlugin, FetchImageHelper):
    @pytest.fixture
    def settings(self):
        return Settings()

    @pytest.fixture
    def source(self):
        return fetchart.ITunesStore(logger, self.plugin.config)

    @pytest.fixture
    def album(self):
        return Album(albumartist="some artist", album="some album")

    def test_itunesstore_finds_image(
        self,
        source: fetchart.ITunesStore,
        settings: Settings,
        album,
        image_response_mocker: ImageResponseMocker,
    ):
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
        image_response_mocker.add(
            fetchart.ITunesStore.API_URL,
            body=json,
            content_type="application/json",
        )
        candidate = next(source.get(album, settings, []))
        assert candidate.url == "url_to_the_image"
        assert candidate.match == fetchart.MetadataMatch.EXACT

    def test_itunesstore_no_result(
        self,
        source: fetchart.ITunesStore,
        settings: Settings,
        album: Album,
        image_response_mocker: ImageResponseMocker,
        caplog: pytest.LogCaptureFixture,
    ):
        json = '{"results": []}'
        image_response_mocker.add(
            fetchart.ITunesStore.API_URL,
            body=json,
            content_type="application/json",
        )
        expected = "got no results"

        with caplog.at_level("DEBUG", logger="beets.test_art"):
            with pytest.raises(StopIteration):
                next(source.get(album, settings, []))
        assert expected in caplog.messages[1]

    def test_itunesstore_requestexception(
        self,
        source: fetchart.ITunesStore,
        settings: Settings,
        album: Album,
        image_response_mocker: ImageResponseMocker,
        caplog: pytest.LogCaptureFixture,
    ):
        image_response_mocker.responses_mock.add(
            responses.GET,
            fetchart.ITunesStore.API_URL,
            json={"error": "not found"},
            status=404,
        )
        expected = "iTunes search failed: 404 Client Error"

        with caplog.at_level("DEBUG", logger="beets.test_art"):
            with pytest.raises(StopIteration):
                next(source.get(album, settings, []))
        assert expected in caplog.messages[1]

    def test_itunesstore_fallback_match(
        self,
        source: fetchart.ITunesStore,
        settings: Settings,
        album: Album,
        image_response_mocker: ImageResponseMocker,
    ):
        json = """{
                    "results":
                        [
                            {
                                "collectionName": "some album",
                                "artworkUrl100": "url_to_the_image"
                            }
                        ]
                  }"""
        image_response_mocker.add(
            fetchart.ITunesStore.API_URL,
            body=json,
            content_type="application/json",
        )
        candidate = next(source.get(album, settings, []))
        assert candidate.url == "url_to_the_image"
        assert candidate.match == fetchart.MetadataMatch.FALLBACK

    def test_itunesstore_returns_result_without_artwork(
        self,
        source: fetchart.ITunesStore,
        settings: Settings,
        album: Album,
        image_response_mocker: ImageResponseMocker,
        caplog: pytest.LogCaptureFixture,
    ):
        json = """{
                    "results":
                        [
                            {
                                "artistName": "some artist",
                                "collectionName": "some album"
                            }
                        ]
                  }"""
        image_response_mocker.add(
            fetchart.ITunesStore.API_URL,
            body=json,
            content_type="application/json",
        )
        expected = "Malformed itunes candidate"

        with caplog.at_level("DEBUG", logger="beets.test_art"):
            with pytest.raises(StopIteration):
                next(source.get(album, settings, []))
        assert expected in caplog.messages[1]

    def test_itunesstore_returns_no_result_when_error_received(
        self,
        source: fetchart.ITunesStore,
        settings: Settings,
        album: Album,
        image_response_mocker: ImageResponseMocker,
        caplog: pytest.LogCaptureFixture,
    ):
        json = '{"error": {"errors": [{"reason": "some reason"}]}}'
        image_response_mocker.add(
            fetchart.ITunesStore.API_URL,
            body=json,
            content_type="application/json",
        )
        expected = "not found in json. Fields are"

        with caplog.at_level("DEBUG", logger="beets.test_art"):
            with pytest.raises(StopIteration):
                next(source.get(album, settings, []))
        assert expected in caplog.messages[1]

    def test_itunesstore_returns_no_result_with_malformed_response(
        self,
        source: fetchart.ITunesStore,
        settings: Settings,
        album: Album,
        image_response_mocker: ImageResponseMocker,
        caplog: pytest.LogCaptureFixture,
    ):
        json = """bla blup"""
        image_response_mocker.add(
            fetchart.ITunesStore.API_URL,
            body=json,
            content_type="application/json",
        )
        expected = "Could not decode json response:"

        with caplog.at_level("DEBUG", logger="beets.test_art"):
            with pytest.raises(StopIteration):
                next(source.get(album, settings, []))
        assert expected in caplog.messages[1]


class TestGoogleImage(UseThePlugin, FetchImageHelper):
    @pytest.fixture
    def settings(self):
        return Settings()

    @pytest.fixture
    def source(self):
        return fetchart.GoogleImages(logger, self.plugin.config)

    def test_google_art_finds_image(
        self,
        source: fetchart.GoogleImages,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ):
        album = Album(albumartist="some artist", album="some album")
        json = '{"items": [{"link": "url_to_the_image"}]}'
        image_response_mocker.add(
            fetchart.GoogleImages.URL,
            body=json,
            content_type="application/json",
        )
        candidate = next(source.get(album, settings, []))
        assert candidate.url == "url_to_the_image"

    def test_google_art_returns_no_result_when_error_received(
        self,
        source: fetchart.GoogleImages,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ):
        album = Album(albumartist="some artist", album="some album")
        json = '{"error": {"errors": [{"reason": "some reason"}]}}'
        image_response_mocker.add(
            fetchart.GoogleImages.URL,
            body=json,
            content_type="application/json",
        )
        with pytest.raises(StopIteration):
            next(source.get(album, settings, []))

    def test_google_art_returns_no_result_with_malformed_response(
        self,
        source: fetchart.GoogleImages,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ):
        album = Album(albumartist="some artist", album="some album")
        json = """bla blup"""
        image_response_mocker.add(
            fetchart.GoogleImages.URL,
            body=json,
            content_type="application/json",
        )
        with pytest.raises(StopIteration):
            next(source.get(album, settings, []))


class TestCoverArtArchive(UseThePlugin, FetchImageHelper, CAAData):
    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(maxwidth=0)

    @pytest.fixture
    def source(self) -> fetchart.CoverArtArchive:
        return fetchart.CoverArtArchive(logger, self.plugin.config)

    def test_caa_finds_image(
        self,
        source: fetchart.CoverArtArchive,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ):
        album = Album(
            mb_albumid=self.MBID_RELASE, mb_releasegroupid=self.MBID_GROUP
        )
        image_response_mocker.add(self.RELEASE_URL, body=self.RESPONSE_RELEASE)
        image_response_mocker.add(self.GROUP_URL, body=self.RESPONSE_GROUP)
        candidates = list(source.get(album, settings, []))
        assert len(candidates) == 3
        assert len(image_response_mocker.responses_mock.calls) == 2
        assert (
            image_response_mocker.responses_mock.calls[0].request.url
            == self.RELEASE_URL
        )

    def test_fetchart_uses_caa_pre_sized_maxwidth_thumbs(
        self,
        source: fetchart.CoverArtArchive,
        image_response_mocker: ImageResponseMocker,
    ):
        # CAA provides pre-sized thumbnails of width 250px, 500px, and 1200px
        # We only test with one of them here
        maxwidth = 1200
        settings = Settings(maxwidth=maxwidth)

        album = Album(
            mb_albumid=self.MBID_RELASE, mb_releasegroupid=self.MBID_GROUP
        )
        image_response_mocker.add(self.RELEASE_URL, body=self.RESPONSE_RELEASE)
        image_response_mocker.add(self.GROUP_URL, body=self.RESPONSE_GROUP)
        candidates = list(source.get(album, settings, []))
        assert len(candidates) == 3
        for candidate in candidates:
            assert candidate.url is not None
            assert f"-{maxwidth}.jpg" in candidate.url

    def test_caa_finds_image_if_maxwidth_is_set_and_thumbnails_is_empty(
        self,
        source: fetchart.CoverArtArchive,
        image_response_mocker: ImageResponseMocker,
    ):
        # CAA provides pre-sized thumbnails of width 250px, 500px, and 1200px
        # We only test with one of them here
        maxwidth = 1200
        settings = Settings(maxwidth=maxwidth)

        album = Album(
            mb_albumid=self.MBID_RELASE, mb_releasegroupid=self.MBID_GROUP
        )
        image_response_mocker.add(
            self.RELEASE_URL, body=self.RESPONSE_RELEASE_WITHOUT_THUMBNAILS
        )
        image_response_mocker.add(
            self.GROUP_URL, body=self.RESPONSE_GROUP_WITHOUT_THUMBNAILS
        )
        candidates = list(source.get(album, settings, []))
        assert len(candidates) == 3
        for candidate in candidates:
            assert candidate.url is not None
            assert f"-{maxwidth}.jpg" not in candidate.url


class TestFanartTV(UseThePlugin, FetchImageHelper):
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

    @pytest.fixture
    def settings(self):
        return Settings(maxwidth=0)

    @pytest.fixture
    def source(self):
        return fetchart.FanartTV(logger, self.plugin.config)

    def test_fanarttv_finds_image(
        self,
        source: fetchart.FanartTV,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ):
        album: Album = Album(mb_releasegroupid="thereleasegroupid")
        image_response_mocker.add(
            f"{fetchart.FanartTV.API_ALBUMS}thereleasegroupid",
            body=self.RESPONSE_MULTIPLE,
            content_type="application/json",
        )
        candidate = next(source.get(album, settings, []))
        assert candidate.url == "http://example.com/1.jpg"

    def test_fanarttv_returns_no_result_when_error_received(
        self,
        source: fetchart.FanartTV,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ):
        album = Album(mb_releasegroupid="thereleasegroupid")
        image_response_mocker.add(
            f"{fetchart.FanartTV.API_ALBUMS}thereleasegroupid",
            body=self.RESPONSE_ERROR,
            content_type="application/json",
        )
        with pytest.raises(StopIteration):
            next(source.get(album, settings, []))

    def test_fanarttv_returns_no_result_with_malformed_response(
        self,
        source: fetchart.FanartTV,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ):
        album = Album(mb_releasegroupid="thereleasegroupid")
        image_response_mocker.add(
            f"{fetchart.FanartTV.API_ALBUMS}thereleasegroupid",
            body=self.RESPONSE_MALFORMED,
            content_type="application/json",
        )
        with pytest.raises(StopIteration):
            next(source.get(album, settings, []))

    def test_fanarttv_only_other_images(
        self,
        source: fetchart.FanartTV,
        settings: Settings,
        image_response_mocker: ImageResponseMocker,
    ):
        # The source used to fail when there were images present, but no cover
        album = Album(mb_releasegroupid="thereleasegroupid")
        image_response_mocker.add(
            f"{fetchart.FanartTV.API_ALBUMS}thereleasegroupid",
            body=self.RESPONSE_NO_ART,
            content_type="application/json",
        )
        with pytest.raises(StopIteration):
            next(source.get(album, settings, []))


class TestArtImporter(UseThePlugin):
    @pytest.fixture(autouse=True)
    def _setup(self, setup_plugin):

        # Mock the album art fetcher to always return our test file.
        self.art_file = self.temp_dir_path / "tmpcover.jpg"
        self.art_file.touch()
        self.old_afa = self.plugin.art_for_album
        self.afa_response = fetchart.Candidate(
            logger, source_name="test", path=self.art_file
        )

        def art_for_album(i, p, local_only=False):
            return self.afa_response

        self.plugin.art_for_album = art_for_album

        # Test library.
        os.mkdir(syspath(os.path.join(self.libdir, b"album")))
        itempath = os.path.join(self.libdir, b"album", b"test.mp3")
        shutil.copyfile(
            syspath(os.path.join(_common.RSRC, b"full.mp3")), syspath(itempath)
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
        self.task.set_choice(AlbumMatch(Distance(), info, {}))
        yield
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
            logger, source_name="test", path=artdest
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


class AlbumArtOperationMixin(UseThePlugin):
    """Base test case for album art operations.

    Provides common setup for testing album art processing operations by setting
    up a mock filesystem source that returns a predefined test image.
    """

    IMAGE_PATH = os.path.join(_common.RSRC, b"abbey-similar.jpg")
    IMAGE_FILESIZE = os.stat(util.syspath(IMAGE_PATH)).st_size
    IMAGE_WIDTH = 500
    IMAGE_HEIGHT = 490
    IMAGE_WIDTH_HEIGHT_DIFF = IMAGE_WIDTH - IMAGE_HEIGHT

    @pytest.fixture(autouse=True, scope="class")
    def fs_mock(self, cleanup):
        def fs_source_get(_self, album, settings, paths):
            if paths:
                yield fetchart.Candidate(
                    logger, source_name=_self.ID, path=self.IMAGE_PATH
                )

        with patch("beetsplug.fetchart.FileSystem.get", fs_source_get):
            yield

    def get_album_art(self):
        return self.plugin.art_for_album(Album(), [""], True)


class TestAlbumArtOperationConfiguration(AlbumArtOperationMixin):
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


class TestAlbumArtPerformOperation(AlbumArtOperationMixin):
    """Test that the art is resized and deinterlaced if necessary."""

    @pytest.fixture
    def resizer_mock(self):
        with patch.object(
            ArtResizer.shared, "resize", return_value=self.IMAGE_PATH
        ) as mocked:
            yield mocked

    @pytest.fixture
    def deinterlacer_mock(self):
        with patch.object(
            ArtResizer.shared, "deinterlace", return_value=self.IMAGE_PATH
        ) as mocked:
            yield mocked

    def test_resize(self, resizer_mock: MagicMock):
        self.plugin.maxwidth = self.IMAGE_WIDTH / 2
        assert self.get_album_art()
        resizer_mock.assert_called_once()

    def test_file_resized(self, resizer_mock: MagicMock):
        self.plugin.max_filesize = self.IMAGE_FILESIZE // 2
        assert self.get_album_art()
        resizer_mock.assert_called_once()

    def test_file_not_resized(self, resizer_mock: MagicMock):
        self.plugin.max_filesize = self.IMAGE_FILESIZE
        assert self.get_album_art()
        resizer_mock.assert_not_called()

    def test_file_resized_but_not_scaled(self, resizer_mock: MagicMock):
        self.plugin.maxwidth = self.IMAGE_WIDTH * 2
        self.plugin.max_filesize = self.IMAGE_FILESIZE // 2
        assert self.get_album_art()
        resizer_mock.assert_called_once()

    def test_file_resized_and_scaled(self, resizer_mock: MagicMock):
        self.plugin.maxwidth = self.IMAGE_WIDTH / 2
        self.plugin.max_filesize = self.IMAGE_FILESIZE // 2
        assert self.get_album_art()
        assert resizer_mock.call_count == 2

    def test_deinterlaced(self, deinterlacer_mock: MagicMock):
        self.plugin.deinterlace = True
        assert self.get_album_art()
        deinterlacer_mock.assert_called_once()

    def test_not_deinterlaced(self, deinterlacer_mock: MagicMock):
        self.plugin.deinterlace = False
        assert self.get_album_art()
        deinterlacer_mock.assert_not_called()

    def test_deinterlaced_and_resized(
        self, resizer_mock: MagicMock, deinterlacer_mock: MagicMock
    ):
        self.plugin.maxwidth = self.IMAGE_WIDTH / 2
        self.plugin.deinterlace = True
        assert self.get_album_art()
        deinterlacer_mock.assert_called_once()
        resizer_mock.assert_called_once()


class TestDeprecatedConfig:
    """While refactoring the plugin, the remote_priority option was deprecated,
    and a new codepath should translate its effect. Check that it actually does
    so.
    """

    # If we subclassed UseThePlugin, the configuration change would either be
    # overwritten by BeetsTestCase or be set after constructing the
    # plugin object
    @pytest.fixture(autouse=True)
    def setup(self):
        config["fetchart"]["remote_priority"] = True
        self.plugin = fetchart.FetchArtPlugin()

    def test_moves_filesystem_to_end(self):
        assert isinstance(self.plugin.sources[-1], fetchart.FileSystem)


class TestEnforceRatioConfig:
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
