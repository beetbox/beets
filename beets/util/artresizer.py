# This file is part of beets.
# Copyright 2016, Fabrice Laporte
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

"""Abstraction layer to resize images using PIL, ImageMagick, or a
public resizing proxy if neither is available.
"""

from __future__ import annotations

import os
import os.path
import platform
import re
import subprocess
from abc import ABC, abstractmethod
from enum import Enum
from itertools import chain
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlencode

from beets import logging, util
from beets.util import (
    LazySharedInstance,
    displayable_path,
    get_temp_filename,
    syspath,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

PROXY_URL = "https://images.weserv.nl/"

log = logging.getLogger("beets")


def resize_url(url: str, maxwidth: int, quality: int = 0) -> str:
    """Return a proxied image URL that resizes the original image to
    maxwidth (preserving aspect ratio).
    """
    params = {
        "url": url.replace("http://", ""),
        "w": maxwidth,
    }

    if quality > 0:
        params["q"] = quality

    return f"{PROXY_URL}?{urlencode(params)}"


class LocalBackendNotAvailableError(Exception):
    pass


# Singleton pattern that the typechecker understands:
# https://peps.python.org/pep-0484/#support-for-singleton-types-in-unions
class NotAvailable(Enum):
    token = 0


_NOT_AVAILABLE = NotAvailable.token


class LocalBackend(ABC):
    NAME: ClassVar[str]

    @classmethod
    @abstractmethod
    def version(cls) -> Any:
        """Return the backend version if its dependencies are satisfied or
        raise `LocalBackendNotAvailableError`.
        """
        pass

    @classmethod
    def available(cls) -> bool:
        """Return `True` this backend's dependencies are satisfied and it can
        be used, `False` otherwise."""
        try:
            cls.version()
            return True
        except LocalBackendNotAvailableError:
            return False

    @abstractmethod
    def resize(
        self,
        maxwidth: int,
        path_in: bytes,
        path_out: bytes | None = None,
        quality: int = 0,
        max_filesize: int = 0,
    ) -> bytes:
        """Resize an image to the given width and return the output path.

        On error, logs a warning and returns `path_in`.
        """
        pass

    @abstractmethod
    def get_size(self, path_in: bytes) -> tuple[int, int] | None:
        """Return the (width, height) of the image or None if unavailable."""
        pass

    @abstractmethod
    def deinterlace(
        self,
        path_in: bytes,
        path_out: bytes | None = None,
    ) -> bytes:
        """Remove interlacing from an image and return the output path.

        On error, logs a warning and returns `path_in`.
        """
        pass

    @abstractmethod
    def get_format(self, path_in: bytes) -> str | None:
        """Return the image format (e.g., 'PNG') or None if undetectable."""
        pass

    @abstractmethod
    def convert_format(
        self,
        source: bytes,
        target: bytes,
        deinterlaced: bool,
    ) -> bytes:
        """Convert an image to a new format and return the new file path.

        On error, logs a warning and returns `source`.
        """
        pass

    @property
    def can_compare(self) -> bool:
        """Indicate whether image comparison is supported by this backend."""
        return False

    def compare(
        self,
        im1: bytes,
        im2: bytes,
        compare_threshold: float,
    ) -> bool | None:
        """Compare two images and return `True` if they are similar enough, or
        `None` if there is an error.

        This must only be called if `self.can_compare()` returns `True`.
        """
        # It is an error to call this when ArtResizer.can_compare is not True.
        raise NotImplementedError()

    @property
    def can_write_metadata(self) -> bool:
        """Indicate whether writing metadata to images is supported."""
        return False

    def write_metadata(self, file: bytes, metadata: Mapping[str, str]) -> None:
        """Write key-value metadata into the image file.

        This must only be called if `self.can_write_metadata()` returns `True`.
        """
        # It is an error to call this when ArtResizer.can_write_metadata is not True.
        raise NotImplementedError()


class IMBackend(LocalBackend):
    NAME = "ImageMagick"

    # These fields are used as a cache for `version()`. `_legacy` indicates
    # whether the modern `magick` binary is available or whether to fall back
    # to the old-style `convert`, `identify`, etc. commands.
    _version: tuple[int, int, int] | NotAvailable | None = None
    _legacy: bool | None = None

    @classmethod
    def version(cls) -> tuple[int, int, int]:
        """Obtain and cache ImageMagick version.

        Raises `LocalBackendNotAvailableError` if not available.
        """
        if cls._version is None:
            for cmd_name, legacy in (("magick", False), ("convert", True)):
                try:
                    out = util.command_output([cmd_name, "--version"]).stdout
                except (subprocess.CalledProcessError, OSError) as exc:
                    log.debug("ImageMagick version check failed: {}", exc)
                    cls._version = _NOT_AVAILABLE
                else:
                    if b"imagemagick" in out.lower():
                        pattern = rb".+ (\d+)\.(\d+)\.(\d+).*"
                        match = re.search(pattern, out)
                        if match:
                            cls._version = (
                                int(match.group(1)),
                                int(match.group(2)),
                                int(match.group(3)),
                            )
                            cls._legacy = legacy

        # cls._version is never None here, but mypy doesn't get that
        if cls._version is _NOT_AVAILABLE or cls._version is None:
            raise LocalBackendNotAvailableError()
        else:
            return cls._version

    convert_cmd: list[str]
    identify_cmd: list[str]
    compare_cmd: list[str]

    def __init__(self) -> None:
        """Initialize a wrapper around ImageMagick for local image operations.

        Stores the ImageMagick version and legacy flag. If ImageMagick is not
        available, raise an Exception.
        """
        self.version()

        # Use ImageMagick's magick binary when it's available.
        # If it's not, fall back to the older, separate convert
        # and identify commands.
        if self._legacy:
            self.convert_cmd = ["convert"]
            self.identify_cmd = ["identify"]
            self.compare_cmd = ["compare"]
        else:
            self.convert_cmd = ["magick"]
            self.identify_cmd = ["magick", "identify"]
            self.compare_cmd = ["magick", "compare"]

    def resize(
        self,
        maxwidth: int,
        path_in: bytes,
        path_out: bytes | None = None,
        quality: int = 0,
        max_filesize: int = 0,
    ) -> bytes:
        """Resize using ImageMagick.

        Use the ``magick`` program or ``convert`` on older versions. Return
        the output path of resized image.
        """
        if not path_out:
            path_out = get_temp_filename(__name__, "resize_IM_", path_in)

        log.debug(
            "artresizer: ImageMagick resizing {} to {}",
            displayable_path(path_in),
            displayable_path(path_out),
        )

        # "-resize WIDTHx>" shrinks images with the width larger
        # than the given width while maintaining the aspect ratio
        # with regards to the height.
        # ImageMagick already seems to default to no interlace, but we include
        # it here for the sake of explicitness.
        cmd: list[str] = self.convert_cmd + [
            syspath(path_in, prefix=False),
            "-resize",
            f"{maxwidth}x>",
            "-interlace",
            "none",
        ]

        if quality > 0:
            cmd += ["-quality", f"{quality}"]

        # "-define jpeg:extent=SIZEb" sets the target filesize for imagemagick
        # to SIZE in bytes.
        if max_filesize > 0:
            cmd += ["-define", f"jpeg:extent={max_filesize}b"]

        cmd.append(syspath(path_out, prefix=False))

        try:
            util.command_output(cmd)
        except subprocess.CalledProcessError:
            log.warning(
                "artresizer: IM convert failed for {}",
                displayable_path(path_in),
            )
            return path_in

        return path_out

    def get_size(self, path_in: bytes) -> tuple[int, int] | None:
        cmd: list[str] = self.identify_cmd + [
            "-format",
            "%w %h",
            syspath(path_in, prefix=False),
        ]

        try:
            out = util.command_output(cmd).stdout
        except subprocess.CalledProcessError as exc:
            log.warning("ImageMagick size query failed")
            log.debug(
                "`convert` exited with (status {.returncode}) when "
                "getting size with command {}:\n{}",
                exc,
                cmd,
                exc.output.strip(),
            )
            return None
        try:
            size = tuple(map(int, out.split(b" ")))
        except IndexError:
            log.warning("Could not understand IM output: {0!r}", out)
            return None

        if len(size) != 2:
            log.warning("Could not understand IM output: {0!r}", out)
            return None

        return size

    def deinterlace(
        self,
        path_in: bytes,
        path_out: bytes | None = None,
    ) -> bytes:
        if not path_out:
            path_out = get_temp_filename(__name__, "deinterlace_IM_", path_in)

        cmd = self.convert_cmd + [
            syspath(path_in, prefix=False),
            "-interlace",
            "none",
            syspath(path_out, prefix=False),
        ]

        try:
            util.command_output(cmd)
            return path_out
        except subprocess.CalledProcessError:
            # FIXME: Should probably issue a warning?
            return path_in

    def get_format(self, path_in: bytes) -> str | None:
        cmd = self.identify_cmd + ["-format", "%[magick]", syspath(path_in)]

        try:
            # Image formats should really only be ASCII strings such as "PNG",
            # if anything else is returned, something is off and we return
            # None for safety.
            return util.command_output(cmd).stdout.decode("ascii", "strict")
        except (subprocess.CalledProcessError, UnicodeError):
            # FIXME: Should probably issue a warning?
            return None

    def convert_format(
        self,
        source: bytes,
        target: bytes,
        deinterlaced: bool,
    ) -> bytes:
        cmd = self.convert_cmd + [
            syspath(source),
            *(["-interlace", "none"] if deinterlaced else []),
            syspath(target),
        ]

        try:
            subprocess.check_call(
                cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL
            )
            return target
        except subprocess.CalledProcessError:
            # FIXME: Should probably issue a warning?
            return source

    @property
    def can_compare(self) -> bool:
        return self.version() > (6, 8, 7)

    def compare(
        self,
        im1: bytes,
        im2: bytes,
        compare_threshold: float,
    ) -> bool | None:
        is_windows = platform.system() == "Windows"

        # Converting images to grayscale tends to minimize the weight
        # of colors in the diff score. So we first convert both images
        # to grayscale and then pipe them into the `compare` command.
        # On Windows, ImageMagick doesn't support the magic \\?\ prefix
        # on paths, so we pass `prefix=False` to `syspath`.
        convert_cmd = self.convert_cmd + [
            syspath(im2, prefix=False),
            syspath(im1, prefix=False),
            "-colorspace",
            "gray",
            "MIFF:-",
        ]
        compare_cmd = self.compare_cmd + [
            "-define",
            "phash:colorspaces=sRGB,HCLp",
            "-metric",
            "PHASH",
            "-",
            "null:",
        ]
        log.debug(
            "comparing images with pipeline {} | {}", convert_cmd, compare_cmd
        )
        convert_proc = subprocess.Popen(
            convert_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=not is_windows,
        )
        compare_proc = subprocess.Popen(
            compare_cmd,
            stdin=convert_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=not is_windows,
        )

        # help out mypy
        assert convert_proc.stdout is not None
        assert convert_proc.stderr is not None

        # Check the convert output. We're not interested in the
        # standard output; that gets piped to the next stage.
        convert_proc.stdout.close()
        convert_stderr = convert_proc.stderr.read()
        convert_proc.stderr.close()
        convert_proc.wait()
        if convert_proc.returncode:
            log.debug(
                "ImageMagick convert failed with status {.returncode}: {!r}",
                convert_proc,
                convert_stderr,
            )
            return None

        # Check the compare output.
        stdout, stderr = compare_proc.communicate()
        if compare_proc.returncode:
            if compare_proc.returncode != 1:
                log.debug(
                    "ImageMagick compare failed: {}, {}",
                    displayable_path(im2),
                    displayable_path(im1),
                )
                return None
            out_str = stderr
        else:
            out_str = stdout

        # ImageMagick 7.1.1-44 outputs in a different format.
        if b"(" in out_str and out_str.endswith(b")"):
            # Extract diff from "... (diff)".
            out_str = out_str[out_str.index(b"(") + 1 : -1]

        try:
            phash_diff = float(out_str)
        except ValueError:
            log.debug("IM output is not a number: {0!r}", out_str)
            return None

        log.debug("ImageMagick compare score: {}", phash_diff)
        return phash_diff <= compare_threshold

    @property
    def can_write_metadata(self) -> bool:
        return True

    def write_metadata(self, file: bytes, metadata: Mapping[str, str]) -> None:
        assignments = chain.from_iterable(
            ("-set", k, v) for k, v in metadata.items()
        )
        str_file = os.fsdecode(file)
        command = self.convert_cmd + [str_file, *assignments, str_file]

        util.command_output(command)


class PILBackend(LocalBackend):
    NAME = "PIL"

    @classmethod
    def version(cls) -> None:
        try:
            __import__("PIL", fromlist=["Image"])
        except ImportError:
            raise LocalBackendNotAvailableError()

    def __init__(self) -> None:
        """Initialize a wrapper around PIL for local image operations.

        If PIL is not available, raise an Exception.
        """
        self.version()

    def resize(
        self,
        maxwidth: int,
        path_in: bytes,
        path_out: bytes | None = None,
        quality: int = 0,
        max_filesize: int = 0,
    ) -> bytes:
        """Resize using Python Imaging Library (PIL).  Return the output path
        of resized image.
        """
        if not path_out:
            path_out = get_temp_filename(__name__, "resize_PIL_", path_in)

        from PIL import Image

        log.debug(
            "artresizer: PIL resizing {} to {}",
            displayable_path(path_in),
            displayable_path(path_out),
        )

        try:
            im = Image.open(syspath(path_in))
            size = maxwidth, maxwidth
            im.thumbnail(size, Image.Resampling.LANCZOS)

            if quality == 0:
                # Use PIL's default quality.
                quality = -1

            # progressive=False only affects JPEGs and is the default,
            # but we include it here for explicitness.
            im.save(os.fsdecode(path_out), quality=quality, progressive=False)

            if max_filesize > 0:
                # If maximum filesize is set, we attempt to lower the quality
                # of jpeg conversion by a proportional amount, up to 3 attempts
                # First, set the maximum quality to either provided, or 95
                if quality > 0:
                    lower_qual = quality
                else:
                    lower_qual = 95
                for i in range(5):
                    # 5 attempts is an arbitrary choice
                    filesize = os.stat(syspath(path_out)).st_size
                    log.debug("PIL Pass {} : Output size: {}B", i, filesize)
                    if filesize <= max_filesize:
                        return path_out
                    # The relationship between filesize & quality will be
                    # image dependent.
                    lower_qual -= 10
                    # Restrict quality dropping below 10
                    if lower_qual < 10:
                        lower_qual = 10
                    # Use optimize flag to improve filesize decrease
                    im.save(
                        os.fsdecode(path_out),
                        quality=lower_qual,
                        optimize=True,
                        progressive=False,
                    )
                log.warning(
                    "PIL Failed to resize file to below {}B", max_filesize
                )
                return path_out

            else:
                return path_out
        except OSError:
            log.error(
                "PIL cannot create thumbnail for '{}'",
                displayable_path(path_in),
            )
            return path_in

    def get_size(self, path_in: bytes) -> tuple[int, int] | None:
        from PIL import Image

        try:
            im = Image.open(syspath(path_in))
            return im.size
        except OSError as exc:
            log.error(
                "PIL could not read file {}: {}", displayable_path(path_in), exc
            )
            return None

    def deinterlace(
        self,
        path_in: bytes,
        path_out: bytes | None = None,
    ) -> bytes:
        if not path_out:
            path_out = get_temp_filename(__name__, "deinterlace_PIL_", path_in)

        from PIL import Image

        try:
            im = Image.open(syspath(path_in))
            im.save(os.fsdecode(path_out), progressive=False)
            return path_out
        except OSError:
            # FIXME: Should probably issue a warning?
            return path_in

    def get_format(self, path_in: bytes) -> str | None:
        from PIL import Image, UnidentifiedImageError

        try:
            with Image.open(syspath(path_in)) as im:
                return im.format
        except (
            ValueError,
            TypeError,
            UnidentifiedImageError,
            FileNotFoundError,
        ):
            log.exception("failed to detect image format for {}", path_in)
            return None

    def convert_format(
        self,
        source: bytes,
        target: bytes,
        deinterlaced: bool,
    ) -> bytes:
        from PIL import Image, UnidentifiedImageError

        try:
            with Image.open(syspath(source)) as im:
                im.save(os.fsdecode(target), progressive=not deinterlaced)
                return target
        except (
            ValueError,
            TypeError,
            UnidentifiedImageError,
            FileNotFoundError,
            OSError,
        ):
            log.exception("failed to convert image {} -> {}", source, target)
            return source

    @property
    def can_compare(self) -> bool:
        return False

    def compare(
        self,
        im1: bytes,
        im2: bytes,
        compare_threshold: float,
    ) -> bool | None:
        # It is an error to call this when ArtResizer.can_compare is not True.
        raise NotImplementedError()

    @property
    def can_write_metadata(self) -> bool:
        return True

    def write_metadata(self, file: bytes, metadata: Mapping[str, str]) -> None:
        from PIL import Image, PngImagePlugin

        # FIXME: Detect and handle other file types (currently, the only user
        # is the thumbnails plugin, which generates PNG images).
        im = Image.open(syspath(file))
        meta = PngImagePlugin.PngInfo()
        for k, v in metadata.items():
            meta.add_text(k, v, zip=False)
        im.save(os.fsdecode(file), "PNG", pnginfo=meta)


BACKEND_CLASSES: list[type[LocalBackend]] = [
    IMBackend,
    PILBackend,
]


class ArtResizer:
    """A class that dispatches image operations to an available backend."""

    local_method: LocalBackend | None

    def __init__(self) -> None:
        """Create a resizer object with an inferred method."""
        # Check if a local backend is available, and store an instance of the
        # backend class. Otherwise, fallback to the web proxy.
        for backend_cls in BACKEND_CLASSES:
            try:
                self.local_method = backend_cls()
                log.debug("artresizer: method is {.local_method.NAME}", self)
                break
            except LocalBackendNotAvailableError:
                continue
        else:
            # FIXME: Turn WEBPROXY into a backend class as well to remove all
            # the special casing. Then simply delegate all methods to the
            # backends. (How does proxy_url fit in here, however?)
            # Use an ABC (or maybe a typing Protocol?) for backend
            # methods, such that both individual backends as well as
            # ArtResizer implement it.
            # It should probably be configurable which backends classes to
            # consider, similar to fetchart or lyrics backends (i.e. a list
            # of backends sorted by priority).
            log.debug("artresizer: method is WEBPROXY")
            self.local_method = None

    shared: LazySharedInstance[ArtResizer] = LazySharedInstance()

    @property
    def method(self) -> str:
        if self.local_method is not None:
            return self.local_method.NAME
        else:
            return "WEBPROXY"

    def resize(
        self,
        maxwidth: int,
        path_in: bytes,
        path_out: bytes | None = None,
        quality: int = 0,
        max_filesize: int = 0,
    ) -> bytes:
        """Manipulate an image file according to the method, returning a
        new path. For PIL or IMAGEMAGIC methods, resizes the image to a
        temporary file and encodes with the specified quality level.
        For WEBPROXY, returns `path_in` unmodified.
        """
        if self.local_method is not None:
            return self.local_method.resize(
                maxwidth,
                path_in,
                path_out,
                quality=quality,
                max_filesize=max_filesize,
            )
        else:
            # Handled by `proxy_url` already.
            return path_in

    def deinterlace(
        self,
        path_in: bytes,
        path_out: bytes | None = None,
    ) -> bytes:
        """Deinterlace an image.

        Only available locally.
        """
        if self.local_method is not None:
            return self.local_method.deinterlace(path_in, path_out)
        else:
            # FIXME: Should probably issue a warning?
            return path_in

    def proxy_url(self, maxwidth: int, url: str, quality: int = 0) -> str:
        """Modifies an image URL according the method, returning a new
        URL. For WEBPROXY, a URL on the proxy server is returned.
        Otherwise, the URL is returned unmodified.
        """
        if self.local:
            # Going to be handled by `resize()`.
            return url
        else:
            return resize_url(url, maxwidth, quality)

    @property
    def local(self) -> bool:
        """A boolean indicating whether the resizing method is performed
        locally (i.e., PIL or ImageMagick).
        """
        return self.local_method is not None

    def get_size(self, path_in: bytes) -> tuple[int, int] | None:
        """Return the size of an image file as an int couple (width, height)
        in pixels.

        Only available locally.
        """
        if self.local_method is not None:
            return self.local_method.get_size(path_in)
        else:
            raise RuntimeError(
                "image cannot be obtained without artresizer backend"
            )

    def get_format(self, path_in: bytes) -> str | None:
        """Returns the format of the image as a string.

        Only available locally.
        """
        if self.local_method is not None:
            return self.local_method.get_format(path_in)
        else:
            # FIXME: Should probably issue a warning?
            return None

    def reformat(
        self,
        path_in: bytes,
        new_format: str,
        deinterlaced: bool = True,
    ) -> bytes:
        """Converts image to desired format, updating its extension, but
        keeping the same filename.

        Only available locally.
        """
        if self.local_method is None:
            # FIXME: Should probably issue a warning?
            return path_in

        new_format = new_format.lower()
        # A nonexhaustive map of image "types" to extensions overrides
        new_format = {
            "jpeg": "jpg",
        }.get(new_format, new_format)

        fname, ext = os.path.splitext(path_in)
        path_new = fname + b"." + new_format.encode("utf8")

        # allows the exception to propagate, while still making sure a changed
        # file path was removed
        result_path = path_in
        try:
            result_path = self.local_method.convert_format(
                path_in, path_new, deinterlaced
            )
        finally:
            if result_path != path_in:
                os.unlink(path_in)
        return result_path

    @property
    def can_compare(self) -> bool:
        """A boolean indicating whether image comparison is available"""

        if self.local_method is not None:
            return self.local_method.can_compare
        else:
            return False

    def compare(
        self,
        im1: bytes,
        im2: bytes,
        compare_threshold: float,
    ) -> bool | None:
        """Return a boolean indicating whether two images are similar.

        Only available locally.
        """
        if self.local_method is not None:
            return self.local_method.compare(im1, im2, compare_threshold)
        else:
            # FIXME: Should probably issue a warning?
            return None

    @property
    def can_write_metadata(self) -> bool:
        """A boolean indicating whether writing image metadata is supported."""

        if self.local_method is not None:
            return self.local_method.can_write_metadata
        else:
            return False

    def write_metadata(self, file: bytes, metadata: Mapping[str, str]) -> None:
        """Write key-value metadata to the image file.

        Only available locally. Currently, expects the image to be a PNG file.
        """
        if self.local_method is not None:
            self.local_method.write_metadata(file, metadata)
        else:
            # FIXME: Should probably issue a warning?
            pass
