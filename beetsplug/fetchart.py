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

"""Fetches album art."""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from collections import OrderedDict
from contextlib import closing
from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING, AnyStr, ClassVar, Literal

import confuse
import requests
from mediafile import image_mime_type

from beets import config, importer, plugins, ui, util
from beets.util import bytestring_path, get_temp_filename, sorted_walk, syspath
from beets.util.artresizer import ArtResizer
from beets.util.config import sanitize_pairs

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from beets.importer import ImportSession, ImportTask
    from beets.library import Album, Library
    from beets.logging import BeetsLogger as Logger

try:
    from bs4 import BeautifulSoup, Tag

    HAS_BEAUTIFUL_SOUP = True
except ImportError:
    HAS_BEAUTIFUL_SOUP = False


CONTENT_TYPES = {"image/jpeg": [b"jpg", b"jpeg"], "image/png": [b"png"]}
IMAGE_EXTENSIONS = [ext for exts in CONTENT_TYPES.values() for ext in exts]


class ImageAction(Enum):
    """Indicates whether an image is useable or requires post-processing."""

    BAD = 0
    EXACT = 1
    DOWNSCALE = 2
    DOWNSIZE = 3
    DEINTERLACE = 4
    REFORMAT = 5


class MetadataMatch(Enum):
    """Indicates whether a `Candidate` matches the search criteria exactly."""

    EXACT = 0
    FALLBACK = 1


SourceLocation = Literal["local", "remote"]


class Candidate:
    """Holds information about a matching artwork, deals with validation of
    dimension restrictions and resizing.
    """

    def __init__(
        self,
        log: Logger,
        source_name: str,
        path: None | bytes = None,
        url: None | str = None,
        match: None | MetadataMatch = None,
        size: None | tuple[int, int] = None,
    ):
        self._log = log
        self.path = path
        self.url = url
        self.source_name = source_name
        self._check: None | ImageAction = None
        self.match = match
        self.size = size

    def _validate(
        self,
        plugin: FetchArtPlugin,
        skip_check_for: None | list[ImageAction] = None,
    ) -> ImageAction:
        """Determine whether the candidate artwork is valid based on
        its dimensions (width and ratio).

        `skip_check_for` is a check or list of checks to skip. This is used to
        avoid redundant checks when the candidate has already been
        validated for a particular operation without changing
        plugin configuration.

        Return `ImageAction.BAD` if the file is unusable.
        Return `ImageAction.EXACT` if the file is usable as-is.
        Return `ImageAction.DOWNSCALE` if the file must be rescaled.
        Return `ImageAction.DOWNSIZE` if the file must be resized, and possibly
            also rescaled.
        Return `ImageAction.DEINTERLACE` if the file must be deinterlaced.
        Return `ImageAction.REFORMAT` if the file has to be converted.
        """
        if not self.path:
            return ImageAction.BAD

        if not (
            plugin.enforce_ratio
            or plugin.minwidth
            or plugin.maxwidth
            or plugin.max_filesize
            or plugin.deinterlace
            or plugin.cover_format
        ):
            return ImageAction.EXACT

        # get_size returns None if no local imaging backend is available
        if not self.size:
            self.size = ArtResizer.shared.get_size(self.path)
        self._log.debug("image size: {.size}", self)

        if not self.size:
            self._log.warning(
                "Could not get size of image (please see "
                "documentation for dependencies). "
                "The configuration options `minwidth`, "
                "`enforce_ratio` and `max_filesize` "
                "may be violated."
            )
            return ImageAction.EXACT

        short_edge = min(self.size)
        long_edge = max(self.size)

        # Check minimum dimension.
        if plugin.minwidth and self.size[0] < plugin.minwidth:
            self._log.debug(
                "image too small ({} < {.minwidth})", self.size[0], plugin
            )
            return ImageAction.BAD

        # Check aspect ratio.
        edge_diff = long_edge - short_edge
        if plugin.enforce_ratio:
            if plugin.margin_px:
                if edge_diff > plugin.margin_px:
                    self._log.debug(
                        "image is not close enough to being "
                        "square, ({} - {} > {.margin_px})",
                        long_edge,
                        short_edge,
                        plugin,
                    )
                    return ImageAction.BAD
            elif plugin.margin_percent:
                margin_px = plugin.margin_percent * long_edge
                if edge_diff > margin_px:
                    self._log.debug(
                        "image is not close enough to being "
                        "square, ({} - {} > {})",
                        long_edge,
                        short_edge,
                        margin_px,
                    )
                    return ImageAction.BAD
            elif edge_diff:
                # also reached for margin_px == 0 and margin_percent == 0.0
                self._log.debug(
                    "image is not square ({} != {})", self.size[0], self.size[1]
                )
                return ImageAction.BAD

        # Check maximum dimension.
        downscale = False
        if plugin.maxwidth and self.size[0] > plugin.maxwidth:
            self._log.debug(
                "image needs rescaling ({} > {.maxwidth})", self.size[0], plugin
            )
            downscale = True

        # Check filesize.
        downsize = False
        if plugin.max_filesize:
            filesize = os.stat(syspath(self.path)).st_size
            if filesize > plugin.max_filesize:
                self._log.debug(
                    "image needs resizing ({}B > {.max_filesize}B)",
                    filesize,
                    plugin,
                )
                downsize = True

        # Check image format
        reformat = False
        if plugin.cover_format:
            fmt = ArtResizer.shared.get_format(self.path)
            reformat = fmt != plugin.cover_format
            if reformat:
                self._log.debug(
                    "image needs reformatting: {} -> {.cover_format}",
                    fmt,
                    plugin,
                )

        skip_check_for = skip_check_for or []

        if downscale and (ImageAction.DOWNSCALE not in skip_check_for):
            return ImageAction.DOWNSCALE
        if reformat and (ImageAction.REFORMAT not in skip_check_for):
            return ImageAction.REFORMAT
        if plugin.deinterlace and (
            ImageAction.DEINTERLACE not in skip_check_for
        ):
            return ImageAction.DEINTERLACE
        if downsize and (ImageAction.DOWNSIZE not in skip_check_for):
            return ImageAction.DOWNSIZE
        return ImageAction.EXACT

    def validate(
        self,
        plugin: FetchArtPlugin,
        skip_check_for: None | list[ImageAction] = None,
    ) -> ImageAction:
        self._check = self._validate(plugin, skip_check_for)
        return self._check

    def resize(self, plugin: FetchArtPlugin) -> None:
        """Resize the candidate artwork according to the plugin's
        configuration until it is valid or no further resizing is
        possible.
        """
        # validate the candidate in case it hasn't been done yet
        current_check = self.validate(plugin)
        checks_performed = []

        # we don't want to resize the image if it's valid or bad
        while current_check not in [ImageAction.BAD, ImageAction.EXACT]:
            self._resize(plugin, current_check)
            checks_performed.append(current_check)
            current_check = self.validate(
                plugin, skip_check_for=checks_performed
            )

    def _resize(
        self, plugin: FetchArtPlugin, check: None | ImageAction = None
    ) -> None:
        """Resize the candidate artwork according to the plugin's
        configuration and the specified check.
        """
        # This must only be called when _validate returned something other than
        # ImageAction.Bad or ImageAction.EXACT; then path and size are known.
        assert self.path is not None
        assert self.size is not None

        if check == ImageAction.DOWNSCALE:
            self.path = ArtResizer.shared.resize(
                plugin.maxwidth,
                self.path,
                quality=plugin.quality,
                max_filesize=plugin.max_filesize,
            )
        elif check == ImageAction.DOWNSIZE:
            # dimensions are correct, so maxwidth is set to maximum dimension
            self.path = ArtResizer.shared.resize(
                max(self.size),
                self.path,
                quality=plugin.quality,
                max_filesize=plugin.max_filesize,
            )
        elif check == ImageAction.DEINTERLACE:
            self.path = ArtResizer.shared.deinterlace(self.path)
        elif check == ImageAction.REFORMAT:
            self.path = ArtResizer.shared.reformat(
                self.path,
                plugin.cover_format,
                deinterlaced=plugin.deinterlace,
            )


def _logged_get(log: Logger, *args, **kwargs) -> requests.Response:
    """Like `requests.get`, but logs the effective URL to the specified
    `log` at the `DEBUG` level.

    Use the optional `message` parameter to specify what to log before
    the URL. By default, the string is "getting URL".

    Also sets the User-Agent header to indicate beets.
    """
    # Use some arguments with the `send` call but most with the
    # `Request` construction. This is a cheap, magic-filled way to
    # emulate `requests.get` or, more pertinently,
    # `requests.Session.request`.
    req_kwargs = kwargs
    send_kwargs = {}
    for arg in ("stream", "verify", "proxies", "cert", "timeout"):
        if arg in kwargs:
            send_kwargs[arg] = req_kwargs.pop(arg)
    if "timeout" not in send_kwargs:
        send_kwargs["timeout"] = 10

    # Our special logging message parameter.
    if "message" in kwargs:
        message = kwargs.pop("message")
    else:
        message = "getting URL"

    req = requests.Request("GET", *args, **req_kwargs)

    with requests.Session() as s:
        s.headers = {"User-Agent": "beets"}
        prepped = s.prepare_request(req)
        settings = s.merge_environment_settings(
            prepped.url, {}, None, None, None
        )
        send_kwargs.update(settings)
        log.debug("{}: {.url}", message, prepped)
        return s.send(prepped, **send_kwargs)


class RequestMixin:
    """Adds a Requests wrapper to the class that uses the logger, which
    must be named `self._log`.
    """

    _log: Logger

    def request(self, *args, **kwargs) -> requests.Response:
        """Like `requests.get`, but uses the logger `self._log`.

        See also `_logged_get`.
        """
        return _logged_get(self._log, *args, **kwargs)


# ART SOURCES ################################################################


class ArtSource(RequestMixin, ABC):
    # Specify whether this source fetches local or remote images
    LOC: ClassVar[SourceLocation]
    # A list of methods to match metadata, sorted by descending accuracy
    VALID_MATCHING_CRITERIA: list[str] = ["default"]
    # A human-readable name for the art source
    NAME: ClassVar[str]
    # The key to select the art source in the config. This value will also be
    # stored in the database.
    ID: ClassVar[str]

    def __init__(
        self,
        log: Logger,
        config: confuse.ConfigView,
        match_by: None | list[str] = None,
    ) -> None:
        self._log = log
        self._config = config
        self.match_by = match_by or self.VALID_MATCHING_CRITERIA

    @cached_property
    def description(self) -> str:
        return f"{self.ID}[{', '.join(self.match_by)}]"

    @staticmethod
    def add_default_config(config: confuse.ConfigView) -> None:
        pass

    @classmethod
    def available(cls, log: Logger, config: confuse.ConfigView) -> bool:
        """Return whether or not all dependencies are met and the art source is
        in fact usable.
        """
        return True

    @abstractmethod
    def get(
        self,
        album: Album,
        plugin: FetchArtPlugin,
        paths: None | Sequence[bytes],
    ) -> Iterator[Candidate]:
        pass

    def _candidate(self, **kwargs) -> Candidate:
        return Candidate(source_name=self.ID, log=self._log, **kwargs)

    @abstractmethod
    def fetch_image(self, candidate: Candidate, plugin: FetchArtPlugin) -> None:
        """Fetch the image to a temporary file if it is not already available
        as a local file.

        After calling this, `Candidate.path` is set to the image path if
        successful, or to `None` otherwise.
        """
        pass

    def cleanup(self, candidate: Candidate) -> None:
        pass


class LocalArtSource(ArtSource):
    LOC = "local"

    def fetch_image(self, candidate: Candidate, plugin: FetchArtPlugin) -> None:
        pass


class RemoteArtSource(ArtSource):
    LOC = "remote"

    def fetch_image(self, candidate: Candidate, plugin: FetchArtPlugin) -> None:
        """Downloads an image from a URL and checks whether it seems to
        actually be an image.
        """
        # This must only be called for candidates that were returned by
        # self.get, which are expected to have a url and no path (because they
        # haven't been downloaded yet).
        assert candidate.path is None
        assert candidate.url is not None

        if plugin.maxwidth:
            candidate.url = ArtResizer.shared.proxy_url(
                plugin.maxwidth, candidate.url
            )
        try:
            with closing(
                self.request(
                    candidate.url, stream=True, message="downloading image"
                )
            ) as resp:
                ct = resp.headers.get("Content-Type", None)

                # Download the image to a temporary file. As some servers
                # (notably fanart.tv) have proven to return wrong Content-Types
                # when images were uploaded with a bad file extension, do not
                # rely on it. Instead validate the type using the file magic
                # and only then determine the extension.
                data = resp.iter_content(chunk_size=1024)
                header = b""
                for chunk in data:
                    header += chunk
                    if len(header) >= 32:
                        # The imghdr module will only read 32 bytes, and our
                        # own additions in mediafile even less.
                        break
                else:
                    # server didn't return enough data, i.e. corrupt image
                    return

                real_ct = image_mime_type(header)
                if real_ct is None:
                    # detection by file magic failed, fall back to the
                    # server-supplied Content-Type
                    # Is our type detection failsafe enough to drop this?
                    real_ct = ct

                if real_ct not in CONTENT_TYPES:
                    self._log.debug(
                        "not a supported image: {}",
                        real_ct or "unknown content type",
                    )
                    return

                ext = b"." + CONTENT_TYPES[real_ct][0]

                if real_ct != ct:
                    self._log.warning(
                        "Server specified {}, but returned a "
                        "{} image. Correcting the extension "
                        "to {}",
                        ct,
                        real_ct,
                        ext,
                    )

                filename = get_temp_filename(__name__, suffix=ext.decode())
                with open(filename, "wb") as fh:
                    # write the first already loaded part of the image
                    fh.write(header)
                    # download the remaining part of the image
                    for chunk in data:
                        fh.write(chunk)
                self._log.debug(
                    "downloaded art to: {}", util.displayable_path(filename)
                )
                candidate.path = util.bytestring_path(filename)
                return

        except (OSError, requests.RequestException, TypeError) as exc:
            # Handling TypeError works around a urllib3 bug:
            # https://github.com/shazow/urllib3/issues/556
            self._log.debug("error fetching art: {}", exc)
            return

    def cleanup(self, candidate: Candidate) -> None:
        if candidate.path:
            try:
                util.remove(path=candidate.path)
            except util.FilesystemError as exc:
                self._log.debug("error cleaning up tmp art: {}", exc)


class CoverArtArchive(RemoteArtSource):
    NAME = "Cover Art Archive"
    ID = "coverart"
    VALID_MATCHING_CRITERIA = ["release", "releasegroup"]
    VALID_THUMBNAIL_SIZES = [250, 500, 1200]

    URL = "https://coverartarchive.org/release/{mbid}"
    GROUP_URL = "https://coverartarchive.org/release-group/{mbid}"

    def get(
        self,
        album: Album,
        plugin: FetchArtPlugin,
        paths: None | Sequence[bytes],
    ) -> Iterator[Candidate]:
        """Return the Cover Art Archive and Cover Art Archive release
        group URLs using album MusicBrainz release ID and release group
        ID.
        """

        def get_image_urls(
            url: str,
            preferred_width: None | str = None,
        ) -> Iterator[str]:
            try:
                response = self.request(url)
            except requests.RequestException:
                self._log.debug("{.NAME}: error receiving response", self)
                return

            try:
                data = response.json()
            except ValueError:
                self._log.debug(
                    "{.NAME}: error loading response: {.text}", self, response
                )
                return

            for item in data.get("images", []):
                try:
                    if "Front" not in item["types"]:
                        continue

                    # If there is a pre-sized thumbnail of the desired size
                    # we select it. Otherwise, we return the raw image.
                    image_url: str = item["image"]
                    if preferred_width is not None:
                        if isinstance(item.get("thumbnails"), dict):
                            image_url = item["thumbnails"].get(
                                preferred_width, image_url
                            )
                    yield image_url
                except KeyError:
                    pass

        release_url = self.URL.format(mbid=album.mb_albumid)
        release_group_url = self.GROUP_URL.format(mbid=album.mb_releasegroupid)

        # Cover Art Archive API offers pre-resized thumbnails at several sizes.
        # If the maxwidth config matches one of the already available sizes
        # fetch it directly instead of fetching the full sized image and
        # resizing it.
        preferred_width = None
        if plugin.maxwidth in self.VALID_THUMBNAIL_SIZES:
            preferred_width = str(plugin.maxwidth)

        if "release" in self.match_by and album.mb_albumid:
            for url in get_image_urls(release_url, preferred_width):
                yield self._candidate(url=url, match=MetadataMatch.EXACT)

        if "releasegroup" in self.match_by and album.mb_releasegroupid:
            for url in get_image_urls(release_group_url, preferred_width):
                yield self._candidate(url=url, match=MetadataMatch.FALLBACK)


class Amazon(RemoteArtSource):
    NAME = "Amazon"
    ID = "amazon"
    URL = "https://images.amazon.com/images/P/{}.{:02d}.LZZZZZZZ.jpg"
    INDICES = (1, 2)

    def get(
        self,
        album: Album,
        plugin: FetchArtPlugin,
        paths: None | Sequence[bytes],
    ) -> Iterator[Candidate]:
        """Generate URLs using Amazon ID (ASIN) string."""
        if album.asin:
            for index in self.INDICES:
                yield self._candidate(
                    url=self.URL.format(album.asin, index),
                    match=MetadataMatch.EXACT,
                )


class AlbumArtOrg(RemoteArtSource):
    NAME = "AlbumArt.org scraper"
    ID = "albumart"
    URL = "https://www.albumart.org/index_detail.php"
    PAT = r'href\s*=\s*"([^>"]*)"[^>]*title\s*=\s*"View larger image"'

    def get(
        self,
        album: Album,
        plugin: FetchArtPlugin,
        paths: None | Sequence[bytes],
    ):
        """Return art URL from AlbumArt.org using album ASIN."""
        if not album.asin:
            return
        # Get the page from albumart.org.
        try:
            resp = self.request(self.URL, params={"asin": album.asin})
            self._log.debug("scraped art URL: {.url}", resp)
        except requests.RequestException:
            self._log.debug("error scraping art page")
            return

        # Search the page for the image URL.
        m = re.search(self.PAT, resp.text)
        if m:
            image_url = m.group(1)
            yield self._candidate(url=image_url, match=MetadataMatch.EXACT)
        else:
            self._log.debug("no image found on page")


class GoogleImages(RemoteArtSource):
    NAME = "Google Images"
    ID = "google"
    URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.key = (self._config["google_key"].get(),)
        self.cx = (self._config["google_engine"].get(),)

    @staticmethod
    def add_default_config(config: confuse.ConfigView):
        config.add(
            {
                "google_key": None,
                "google_engine": "001442825323518660753:hrh5ch1gjzm",
            }
        )
        config["google_key"].redact = True
        config["google_engine"].redact = True

    @classmethod
    def available(cls, log: Logger, config: confuse.ConfigView) -> bool:
        has_key = bool(config["google_key"].get())
        if not has_key:
            log.debug("google: Disabling art source due to missing key")
        return has_key

    def get(
        self,
        album: Album,
        plugin: FetchArtPlugin,
        paths: None | Sequence[bytes],
    ) -> Iterator[Candidate]:
        """Return art URL from google custom search engine
        given an album title and interpreter.
        """
        if not (album.albumartist and album.album):
            return
        search_string = f"{album.albumartist},{album.album}".encode()

        try:
            response = self.request(
                self.URL,
                params={
                    "key": self.key,
                    "cx": self.cx,
                    "q": search_string,
                    "searchType": "image",
                },
            )
        except requests.RequestException:
            self._log.debug("google: error receiving response")
            return

        # Get results using JSON.
        try:
            data = response.json()
        except ValueError:
            self._log.debug("google: error loading response: {.text}", response)
            return

        if "error" in data:
            reason = data["error"]["errors"][0]["reason"]
            self._log.debug("google fetchart error: {}", reason)
            return

        if "items" in data.keys():
            for item in data["items"]:
                yield self._candidate(
                    url=item["link"], match=MetadataMatch.EXACT
                )


class FanartTV(RemoteArtSource):
    """Art from fanart.tv requested using their API"""

    NAME = "fanart.tv"
    ID = "fanarttv"
    API_URL = "https://webservice.fanart.tv/v3/"
    API_ALBUMS = f"{API_URL}music/albums/"
    PROJECT_KEY = "61a7d0ab4e67162b7a0c7c35915cd48e"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_key = self._config["fanarttv_key"].get()

    @staticmethod
    def add_default_config(config: confuse.ConfigView):
        config.add(
            {
                "fanarttv_key": None,
            }
        )
        config["fanarttv_key"].redact = True

    def get(
        self,
        album: Album,
        plugin: FetchArtPlugin,
        paths: None | Sequence[bytes],
    ) -> Iterator[Candidate]:
        if not album.mb_releasegroupid:
            return

        try:
            response = self.request(
                f"{self.API_ALBUMS}{album.mb_releasegroupid}",
                headers={
                    "api-key": self.PROJECT_KEY,
                    "client-key": self.client_key,
                },
            )
        except requests.RequestException:
            self._log.debug("fanart.tv: error receiving response")
            return

        try:
            data = response.json()
        except ValueError:
            self._log.debug(
                "fanart.tv: error loading response: {.text}", response
            )
            return

        if "status" in data and data["status"] == "error":
            if "not found" in data["error message"].lower():
                self._log.debug("fanart.tv: no image found")
            elif "api key" in data["error message"].lower():
                self._log.warning(
                    "fanart.tv: Invalid API key given, please "
                    "enter a valid one in your config file."
                )
            else:
                self._log.debug(
                    "fanart.tv: error on request: {}", data["error message"]
                )
            return

        matches = []
        # can there be more than one releasegroupid per response?
        for mbid, art in data.get("albums", {}).items():
            # there might be more art referenced, e.g. cdart, and an albumcover
            # might not be present, even if the request was successful
            if album.mb_releasegroupid == mbid and "albumcover" in art:
                matches.extend(art["albumcover"])
            # can this actually occur?
            else:
                self._log.debug(
                    "fanart.tv: unexpected mb_releasegroupid in response!"
                )

        matches.sort(key=lambda x: int(x["likes"]), reverse=True)
        for item in matches:
            # fanart.tv has a strict size requirement for album art to be
            # uploaded
            yield self._candidate(
                url=item["url"], match=MetadataMatch.EXACT, size=(1000, 1000)
            )


class ITunesStore(RemoteArtSource):
    NAME = "iTunes Store"
    ID = "itunes"
    API_URL = "https://itunes.apple.com/search"

    def get(
        self,
        album: Album,
        plugin: FetchArtPlugin,
        paths: None | Sequence[bytes],
    ) -> Iterator[Candidate]:
        """Return art URL from iTunes Store given an album title."""
        if not (album.albumartist and album.album):
            return

        payload = {
            "term": f"{album.albumartist} {album.album}",
            "entity": "album",
            "media": "music",
            "limit": 200,
        }
        try:
            r = self.request(self.API_URL, params=payload)
            r.raise_for_status()
        except requests.RequestException as e:
            self._log.debug("iTunes search failed: {}", e)
            return

        try:
            candidates = r.json()["results"]
        except ValueError as e:
            self._log.debug("Could not decode json response: {}", e)
            return
        except KeyError as e:
            self._log.debug(
                "{} not found in json. Fields are {} ", e, list(r.json().keys())
            )
            return

        if not candidates:
            self._log.debug(
                "iTunes search for {!r} got no results", payload["term"]
            )
            return

        if self._config["high_resolution"]:
            image_suffix = "100000x100000-999"
        else:
            image_suffix = "1200x1200bb"

        for c in candidates:
            try:
                if (
                    c["artistName"] == album.albumartist
                    and c["collectionName"] == album.album
                ):
                    art_url = c["artworkUrl100"]
                    art_url = art_url.replace("100x100bb", image_suffix)
                    yield self._candidate(
                        url=art_url, match=MetadataMatch.EXACT
                    )
            except KeyError as e:
                self._log.debug(
                    "Malformed itunes candidate: {} not found in {}",  # NOQA E501
                    e,
                    list(c.keys()),
                )

        try:
            fallback_art_url = candidates[0]["artworkUrl100"]
            fallback_art_url = fallback_art_url.replace(
                "100x100bb", image_suffix
            )
            yield self._candidate(
                url=fallback_art_url, match=MetadataMatch.FALLBACK
            )
        except KeyError as e:
            self._log.debug(
                "Malformed itunes candidate: {} not found in {}",
                e,
                list(c.keys()),
            )


class Wikipedia(RemoteArtSource):
    NAME = "Wikipedia (queried through DBpedia)"
    ID = "wikipedia"
    DBPEDIA_URL = "https://dbpedia.org/sparql"
    WIKIPEDIA_URL = "https://en.wikipedia.org/w/api.php"
    SPARQL_QUERY = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                 PREFIX dbpprop: <http://dbpedia.org/property/>
                 PREFIX owl: <http://dbpedia.org/ontology/>
                 PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                 PREFIX foaf: <http://xmlns.com/foaf/0.1/>

                 SELECT DISTINCT ?pageId ?coverFilename WHERE {{
                   ?subject owl:wikiPageID ?pageId .
                   ?subject dbpprop:name ?name .
                   ?subject rdfs:label ?label .
                   {{ ?subject dbpprop:artist ?artist }}
                     UNION
                   {{ ?subject owl:artist ?artist }}
                   {{ ?artist foaf:name "{artist}"@en }}
                     UNION
                   {{ ?artist dbpprop:name "{artist}"@en }}
                   ?subject rdf:type <http://dbpedia.org/ontology/Album> .
                   ?subject dbpprop:cover ?coverFilename .
                   FILTER ( regex(?name, "{album}", "i") )
                  }}
                 Limit 1"""

    def get(
        self,
        album: Album,
        plugin: FetchArtPlugin,
        paths: None | Sequence[bytes],
    ) -> Iterator[Candidate]:
        if not (album.albumartist and album.album):
            return

        # Find the name of the cover art filename on DBpedia
        cover_filename, page_id = None, None

        try:
            dbpedia_response = self.request(
                self.DBPEDIA_URL,
                params={
                    "format": "application/sparql-results+json",
                    "timeout": 2500,
                    "query": self.SPARQL_QUERY.format(
                        artist=album.albumartist.title(), album=album.album
                    ),
                },
                headers={"content-type": "application/json"},
            )
        except requests.RequestException:
            self._log.debug("dbpedia: error receiving response")
            return

        try:
            data = dbpedia_response.json()
            results = data["results"]["bindings"]
            if results:
                cover_filename = f"File:{results[0]['coverFilename']['value']}"
                page_id = results[0]["pageId"]["value"]
            else:
                self._log.debug("wikipedia: album not found on dbpedia")
        except (ValueError, KeyError, IndexError):
            self._log.debug(
                "wikipedia: error scraping dbpedia response: {.text}",
                dbpedia_response,
            )

        # Ensure we have a filename before attempting to query wikipedia
        if not (cover_filename and page_id):
            return

        # DBPedia sometimes provides an incomplete cover_filename, indicated
        # by the filename having a space before the extension, e.g., 'foo .bar'
        # An additional Wikipedia call can help to find the real filename.
        # This may be removed once the DBPedia issue is resolved, see:
        # https://github.com/dbpedia/extraction-framework/issues/396
        if " ." in cover_filename and "." not in cover_filename.split(" .")[-1]:
            self._log.debug(
                "wikipedia: dbpedia provided incomplete cover_filename"
            )
            lpart, rpart = cover_filename.rsplit(" .", 1)

            # Query all the images in the page
            try:
                wikipedia_response = self.request(
                    self.WIKIPEDIA_URL,
                    params={
                        "format": "json",
                        "action": "query",
                        "continue": "",
                        "prop": "images",
                        "pageids": page_id,
                    },
                    headers={"content-type": "application/json"},
                )
            except requests.RequestException:
                self._log.debug("wikipedia: error receiving response")
                return

            # Try to see if one of the images on the pages matches our
            # incomplete cover_filename
            try:
                data = wikipedia_response.json()
                results = data["query"]["pages"][page_id]["images"]
                for result in results:
                    if re.match(
                        rf"{re.escape(lpart)}.*?\.{re.escape(rpart)}",
                        result["title"],
                    ):
                        cover_filename = result["title"]
                        break
            except (ValueError, KeyError):
                self._log.debug(
                    "wikipedia: failed to retrieve a cover_filename"
                )
                return

        # Find the absolute url of the cover art on Wikipedia
        try:
            wikipedia_response = self.request(
                self.WIKIPEDIA_URL,
                params={
                    "format": "json",
                    "action": "query",
                    "continue": "",
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "titles": cover_filename.encode("utf-8"),
                },
                headers={"content-type": "application/json"},
            )
        except requests.RequestException:
            self._log.debug("wikipedia: error receiving response")
            return

        try:
            data = wikipedia_response.json()
            results = data["query"]["pages"]
            for _, result in results.items():
                image_url = result["imageinfo"][0]["url"]
                yield self._candidate(url=image_url, match=MetadataMatch.EXACT)
        except (ValueError, KeyError, IndexError):
            self._log.debug("wikipedia: error scraping imageinfo")
            return


class FileSystem(LocalArtSource):
    NAME = "Filesystem"
    ID = "filesystem"

    @staticmethod
    def filename_priority(
        filename: AnyStr, cover_names: Sequence[AnyStr]
    ) -> list[int]:
        """Sort order for image names.

        Return indexes of cover names found in the image filename. This
        means that images with lower-numbered and more keywords will have
        higher priority.
        """
        return [idx for (idx, x) in enumerate(cover_names) if x in filename]

    def get(
        self,
        album: Album,
        plugin: FetchArtPlugin,
        paths: None | Sequence[bytes],
    ) -> Iterator[Candidate]:
        """Look for album art files in the specified directories."""
        if not paths:
            return
        cover_names = list(map(util.bytestring_path, plugin.cover_names))
        cover_names_str = b"|".join(cover_names)
        cover_pat = rb"".join([rb"(\b|_)(", cover_names_str, rb")(\b|_)"])

        for path in paths:
            if not os.path.isdir(syspath(path)):
                continue

            # Find all files that look like images in the directory.
            images = []
            ignore = config["ignore"].as_str_seq()
            ignore_hidden = config["ignore_hidden"].get(bool)
            for _, _, files in sorted_walk(
                path, ignore=ignore, ignore_hidden=ignore_hidden
            ):
                for fn in files:
                    fn = bytestring_path(fn)
                    for ext in IMAGE_EXTENSIONS:
                        if fn.lower().endswith(b"." + ext) and os.path.isfile(
                            syspath(os.path.join(path, fn))
                        ):
                            images.append(fn)

            # Look for "preferred" filenames.
            images = sorted(
                images, key=lambda x: self.filename_priority(x, cover_names)
            )
            remaining = []
            for fn in images:
                if re.search(cover_pat, os.path.splitext(fn)[0], re.I):
                    self._log.debug(
                        "using well-named art file {}",
                        util.displayable_path(fn),
                    )
                    yield self._candidate(
                        path=os.path.join(path, fn), match=MetadataMatch.EXACT
                    )
                else:
                    remaining.append(fn)

            # Fall back to any image in the folder.
            if remaining and not plugin.cautious:
                self._log.debug(
                    "using fallback art file {}",
                    util.displayable_path(remaining[0]),
                )
                yield self._candidate(
                    path=os.path.join(path, remaining[0]),
                    match=MetadataMatch.FALLBACK,
                )


class LastFM(RemoteArtSource):
    NAME = "Last.fm"
    ID = "lastfm"

    # Sizes in priority order.
    SIZES = OrderedDict(
        [
            ("mega", (300, 300)),
            ("extralarge", (300, 300)),
            ("large", (174, 174)),
            ("medium", (64, 64)),
            ("small", (34, 34)),
        ]
    )

    API_URL = "https://ws.audioscrobbler.com/2.0"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.key = (self._config["lastfm_key"].get(),)

    @staticmethod
    def add_default_config(config: confuse.ConfigView) -> None:
        config.add(
            {
                "lastfm_key": None,
            }
        )
        config["lastfm_key"].redact = True

    @classmethod
    def available(cls, log: Logger, config: confuse.ConfigView) -> bool:
        has_key = bool(config["lastfm_key"].get())
        if not has_key:
            log.debug("lastfm: Disabling art source due to missing key")
        return has_key

    def get(
        self,
        album: Album,
        plugin: FetchArtPlugin,
        paths: None | Sequence[bytes],
    ) -> Iterator[Candidate]:
        if not album.mb_albumid:
            return

        try:
            response = self.request(
                self.API_URL,
                params={
                    "method": "album.getinfo",
                    "api_key": self.key,
                    "mbid": album.mb_albumid,
                    "format": "json",
                },
            )
        except requests.RequestException:
            self._log.debug("lastfm: error receiving response")
            return

        try:
            data = response.json()

            if "error" in data:
                if data["error"] == 6:
                    self._log.debug(
                        "lastfm: no results for {.mb_albumid}", album
                    )
                else:
                    self._log.error(
                        "lastfm: failed to get album info: {} ({})",
                        data["message"],
                        data["error"],
                    )
            else:
                images = {
                    image["size"]: image["#text"]
                    for image in data["album"]["image"]
                }

                # Provide candidates in order of size.
                for size in self.SIZES.keys():
                    if size in images:
                        yield self._candidate(
                            url=images[size], size=self.SIZES[size]
                        )
        except ValueError:
            self._log.debug("lastfm: error loading response: {.text}", response)
            return


class Spotify(RemoteArtSource):
    NAME = "Spotify"
    ID = "spotify"

    SPOTIFY_ALBUM_URL = "https://open.spotify.com/album/"

    @classmethod
    def available(cls, log: Logger, config: confuse.ConfigView) -> bool:
        if not HAS_BEAUTIFUL_SOUP:
            log.debug(
                "To use Spotify as an album art source, "
                "you must install the beautifulsoup4 module. See "
                "the documentation for further details."
            )
        return HAS_BEAUTIFUL_SOUP

    def get(
        self,
        album: Album,
        plugin: FetchArtPlugin,
        paths: None | Sequence[bytes],
    ) -> Iterator[Candidate]:
        try:
            url = f"{self.SPOTIFY_ALBUM_URL}{album.items().get().spotify_album_id}"
        except AttributeError:
            self._log.debug("Fetchart: no Spotify album ID found")
            return

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            self._log.debug("Error: {!s}", e)
            return

        try:
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
        except ValueError:
            self._log.debug(
                "Spotify: error loading response: {.text}", response
            )
            return

        tag = soup.find("meta", attrs={"property": "og:image"})
        if tag is None or not isinstance(tag, Tag):
            self._log.debug(
                "Spotify: Unexpected response, og:image tag missing"
            )
            return

        image_url = tag["content"]
        yield self._candidate(url=image_url, match=MetadataMatch.EXACT)


class CoverArtUrl(RemoteArtSource):
    # This source is intended to be used with a plugin that sets the
    # cover_art_url field on albums or tracks. Users can also manually update
    # the cover_art_url field using the "set" command. This source will then
    # use that URL to fetch the image.

    NAME = "Cover Art URL"
    ID = "cover_art_url"

    def get(
        self,
        album: Album,
        plugin: FetchArtPlugin,
        paths: None | Sequence[bytes],
    ) -> Iterator[Candidate]:
        image_url = None
        try:
            # look for cover_art_url on album or first track
            if album.get("cover_art_url"):
                image_url = album.cover_art_url
            else:
                image_url = album.items().get().cover_art_url
            self._log.debug("Cover art URL {} found for {}", image_url, album)
        except (AttributeError, TypeError):
            self._log.debug("Cover art URL not found for {}", album)
            return
        if image_url:
            yield self._candidate(url=image_url, match=MetadataMatch.EXACT)
        else:
            self._log.debug("Cover art URL not found for {}", album)
            return


# All art sources. The order they will be tried in is specified by the config.
ART_SOURCES: set[type[ArtSource]] = {
    FileSystem,
    CoverArtArchive,
    ITunesStore,
    AlbumArtOrg,
    Amazon,
    Wikipedia,
    GoogleImages,
    FanartTV,
    LastFM,
    Spotify,
    CoverArtUrl,
}


# PLUGIN LOGIC ###############################################################


class FetchArtPlugin(plugins.BeetsPlugin, RequestMixin):
    PAT_PX = r"(0|[1-9][0-9]*)px"
    PAT_PERCENT = r"(100(\.00?)?|[1-9]?[0-9](\.[0-9]{1,2})?)%"

    def __init__(self) -> None:
        super().__init__()

        # Holds candidates corresponding to downloaded images between
        # fetching them and placing them in the filesystem.
        self.art_candidates: dict[ImportTask, Candidate] = {}

        self.config.add(
            {
                "auto": True,
                "minwidth": 0,
                "maxwidth": 0,
                "quality": 0,
                "max_filesize": 0,
                "enforce_ratio": False,
                "cautious": False,
                "cover_names": ["cover", "front", "art", "album", "folder"],
                "sources": [
                    "filesystem",
                    "coverart",
                    "itunes",
                    "amazon",
                    "albumart",
                    "cover_art_url",
                ],
                "store_source": False,
                "high_resolution": False,
                "deinterlace": False,
                "cover_format": None,
            }
        )
        for source in ART_SOURCES:
            source.add_default_config(self.config)

        self.minwidth = self.config["minwidth"].get(int)
        self.maxwidth = self.config["maxwidth"].get(int)
        self.max_filesize = self.config["max_filesize"].get(int)
        self.quality = self.config["quality"].get(int)

        # allow both pixel and percentage-based margin specifications
        self.enforce_ratio = self.config["enforce_ratio"].get(
            confuse.OneOf(
                [
                    bool,
                    confuse.String(pattern=self.PAT_PX),
                    confuse.String(pattern=self.PAT_PERCENT),
                ]
            )
        )
        self.margin_px = None
        self.margin_percent = None
        self.deinterlace = self.config["deinterlace"].get(bool)
        if isinstance(self.enforce_ratio, str):
            if self.enforce_ratio[-1] == "%":
                self.margin_percent = float(self.enforce_ratio[:-1]) / 100
            elif self.enforce_ratio[-2:] == "px":
                self.margin_px = int(self.enforce_ratio[:-2])
            else:
                # shouldn't happen
                raise confuse.ConfigValueError()
            self.enforce_ratio = True

        cover_names = self.config["cover_names"].as_str_seq()
        self.cover_names = list(map(util.bytestring_path, cover_names))
        self.cautious = self.config["cautious"].get(bool)
        self.store_source = self.config["store_source"].get(bool)

        self.cover_format = self.config["cover_format"].get(
            confuse.Optional(str)
        )

        if self.config["auto"]:
            # Enable two import hooks when fetching is enabled.
            self.import_stages = [self.fetch_art]
            self.register_listener("import_task_files", self.assign_art)

        available_sources = [
            (s_cls.ID, c)
            for s_cls in ART_SOURCES
            if s_cls.available(self._log, self.config)
            for c in s_cls.VALID_MATCHING_CRITERIA
        ]
        sources = sanitize_pairs(
            self.config["sources"].as_pairs(default_value="*"),
            available_sources,
        )

        if "remote_priority" in self.config:
            self._log.warning(
                "The `fetch_art.remote_priority` configuration option has "
                "been deprecated. Instead, place `filesystem` at the end of "
                "your `sources` list."
            )
            if self.config["remote_priority"].get(bool):
                fs = []
                others = []
                for s, c in sources:
                    if s == "filesystem":
                        fs.append((s, c))
                    else:
                        others.append((s, c))
                sources = others + fs

        sources_by_name = {s_cls.ID: s_cls for s_cls in ART_SOURCES}

        self.sources = [
            sources_by_name[s](self._log, self.config, match_by=[c])
            for s, c in sources
        ]

    @staticmethod
    def _is_source_file_removal_enabled() -> bool:
        return config["import"]["delete"].get(bool) or config["import"][
            "move"
        ].get(bool)

    # Asynchronous; after music is added to the library.
    def fetch_art(self, session: ImportSession, task: ImportTask) -> None:
        """Find art for the album being imported."""
        if task.is_album:  # Only fetch art for full albums.
            if task.album.artpath and os.path.isfile(
                syspath(task.album.artpath)
            ):
                # Album already has art (probably a re-import); skip it.
                return
            if task.choice_flag == importer.Action.ASIS:
                # For as-is imports, don't search Web sources for art.
                local = True
            elif task.choice_flag in (
                importer.Action.APPLY,
                importer.Action.RETAG,
            ):
                # Search everywhere for art.
                local = False
            else:
                # For any other choices (e.g., TRACKS), do nothing.
                return

            candidate = self.art_for_album(task.album, task.paths, local)

            if candidate:
                self.art_candidates[task] = candidate

    def _set_art(
        self, album: Album, candidate: Candidate, delete: bool = False
    ) -> None:
        album.set_art(candidate.path, delete)
        if self.store_source:
            # store the source of the chosen artwork in a flexible field
            self._log.debug(
                "Storing art_source for {0.albumartist} - {0.album}", album
            )
            album.art_source = candidate.source_name
        album.store()

    # Synchronous; after music files are put in place.
    def assign_art(self, session: ImportSession, task: ImportTask):
        """Place the discovered art in the filesystem."""
        if task in self.art_candidates:
            candidate = self.art_candidates.pop(task)
            removal_enabled = self._is_source_file_removal_enabled()

            self._set_art(task.album, candidate, not removal_enabled)

            if removal_enabled:
                task.prune(candidate.path)

    # Manual album art fetching.
    def commands(self) -> list[ui.Subcommand]:
        cmd = ui.Subcommand("fetchart", help="download album art")
        cmd.parser.add_option(
            "-f",
            "--force",
            dest="force",
            action="store_true",
            default=False,
            help="re-download art when already present",
        )
        cmd.parser.add_option(
            "-q",
            "--quiet",
            dest="quiet",
            action="store_true",
            default=False,
            help="quiet mode: do not output albums that already have artwork",
        )

        def func(lib: Library, opts, args) -> None:
            self.batch_fetch_art(lib, lib.albums(args), opts.force, opts.quiet)

        cmd.func = func
        return [cmd]

    # Utilities converted from functions to methods on logging overhaul

    def art_for_album(
        self,
        album: Album,
        paths: None | Sequence[bytes],
        local_only: bool = False,
    ) -> None | Candidate:
        """Given an Album object, returns a path to downloaded art for the
        album (or None if no art is found). If `maxwidth`, then images are
        resized to this maximum pixel size. If `quality` then resized images
        are saved at the specified quality level. If `local_only`, then only
        local image files from the filesystem are returned; no network
        requests are made.
        """
        out = None

        for source in self.sources:
            if source.LOC == "local" or not local_only:
                self._log.debug(
                    "trying source {0.description}"
                    " for album {1.albumartist} - {1.album}",
                    source,
                    album,
                )
                # URLs might be invalid at this point, or the image may not
                # fulfill the requirements
                for candidate in source.get(album, self, paths):
                    source.fetch_image(candidate, self)
                    if candidate.validate(self) != ImageAction.BAD:
                        out = candidate
                        assert out.path is not None  # help mypy
                        self._log.debug(
                            "using {.LOC} image {.path}", source, out
                        )
                        break
                    # Remove temporary files for invalid candidates.
                    source.cleanup(candidate)
                if out:
                    break

        if out:
            out.resize(self)

        return out

    def batch_fetch_art(
        self,
        lib: Library,
        albums: Iterable[Album],
        force: bool,
        quiet: bool,
    ) -> None:
        """Fetch album art for each of the albums. This implements the manual
        fetchart CLI command.
        """
        for album in albums:
            if (
                album.artpath
                and not force
                and os.path.isfile(syspath(album.artpath))
            ):
                if not quiet:
                    message = ui.colorize(
                        "text_highlight_minor", "has album art"
                    )
                    self._log.info("{}: {}", album, message)
            else:
                # In ordinary invocations, look for images on the
                # filesystem. When forcing, however, always go to the Web
                # sources.
                local_paths = None if force else [album.path]

                candidate = self.art_for_album(album, local_paths)
                if candidate:
                    self._set_art(album, candidate)
                    message = ui.colorize("text_success", "found album art")
                else:
                    message = ui.colorize("text_error", "no art found")
                self._log.info("{}: {}", album, message)
