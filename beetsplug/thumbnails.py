"""Create freedesktop.org-compliant thumbnails for album folders

This plugin is POSIX-only.
Spec: standards.freedesktop.org/thumbnail-spec/latest/index.html
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import shutil
from hashlib import md5
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from xdg import BaseDirectory

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.util import bytestring_path, displayable_path, syspath
from beets.util.artresizer import ArtResizer

BASE_DIR = os.path.join(BaseDirectory.xdg_cache_home, "thumbnails")
if TYPE_CHECKING:
    import optparse

    from beets.library import Album, Library


NORMAL_DIR = bytestring_path(os.path.join(BASE_DIR, "normal"))
LARGE_DIR = bytestring_path(os.path.join(BASE_DIR, "large"))


class ThumbnailsPlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.config.add({"auto": True, "force": False, "dolphin": False})

        if self.config["auto"] and self._check_local_ok():
            self.register_listener("art_set", self.process_album)

    def commands(self) -> list[Subcommand]:
        thumbnails_command = Subcommand(
            "thumbnails", help="Create album thumbnails"
        )
        thumbnails_command.parser.add_option(
            "-f",
            "--force",
            dest="force",
            action="store_true",
            default=False,
            help="force regeneration of thumbnails deemed fine (existing & "
            "recent enough)",
        )
        thumbnails_command.parser.add_option(
            "--dolphin",
            dest="dolphin",
            action="store_true",
            default=False,
            help="create Dolphin-compatible thumbnail information (for KDE)",
        )
        thumbnails_command.func = self.process_query

        return [thumbnails_command]

    def process_query(
        self, lib: Library, opts: optparse.Values, args: list[str]
    ) -> None:
        self.config.set_args(opts)
        if self._check_local_ok():
            for album in lib.albums(args):
                self.process_album(album)

    def _check_local_ok(self) -> bool:
        """Check that everything is ready:
        - local capability to resize images
        - thumbnail dirs exist (create them if needed)
        - detect whether we'll use PIL or IM
        - detect whether we'll use GIO or Python to get URIs
        """
        if not ArtResizer.shared.local:
            self._log.warning(
                "No local image resizing capabilities, "
                "cannot generate thumbnails"
            )
            return False

        for dir_ in (NORMAL_DIR, LARGE_DIR):
            if not os.path.exists(syspath(dir_)):
                os.makedirs(syspath(dir_))

        if not ArtResizer.shared.can_write_metadata:
            raise RuntimeError(
                f"Thumbnails: ArtResizer backend {ArtResizer.shared.method}"
                f" unexpectedly cannot write image metadata."
            )
        self._log.debug("using {.shared.method} to write metadata", ArtResizer)

        uri_getter: URIGetter = GioURI()
        if not uri_getter.available:
            uri_getter = PathlibURI()
        self._log.debug("using {.name} to compute URIs", uri_getter)
        self.get_uri = uri_getter.uri

        return True

    def process_album(self, album: Album) -> None:
        """Produce thumbnails for the album folder."""
        self._log.debug("generating thumbnail for {}", album)

        artpath = album.artpath
        if not artpath:
            self._log.warning("album {} has no art", album)
            return

        if self.config["dolphin"]:
            self.make_dolphin_cover_thumbnail(album.path, artpath)

        size = ArtResizer.shared.get_size(artpath)
        if not size:
            self._log.warning(
                "problem getting the picture size for {.artpath}", album
            )
            return

        wrote = True
        if max(size) >= 256:
            wrote &= self.make_cover_thumbnail(album, artpath, 256, LARGE_DIR)
        wrote &= self.make_cover_thumbnail(album, artpath, 128, NORMAL_DIR)

        if wrote:
            self._log.info("wrote thumbnail for {}", album)
        else:
            self._log.info("nothing to do for {}", album)

    def make_cover_thumbnail(
        self, album: Album, artpath: bytes, size: int, target_dir: bytes
    ) -> bool:
        """Make a thumbnail of given size for `album` and put it in
        `target_dir`.
        """
        target = os.path.join(target_dir, self.thumbnail_file_name(album.path))

        if (
            os.path.exists(syspath(target))
            and os.stat(syspath(target)).st_mtime
            > os.stat(syspath(artpath)).st_mtime
        ):
            if self.config["force"]:
                self._log.debug(
                    "found a suitable {0}x{0} thumbnail for {1}, "
                    "forcing regeneration",
                    size,
                    album,
                )
            else:
                self._log.debug(
                    "{0}x{0} thumbnail for {1} exists and is recent enough",
                    size,
                    album,
                )
                return False
        resized = ArtResizer.shared.resize(size, artpath, target)
        self.add_tags(artpath, resized)
        shutil.move(syspath(resized), syspath(target))
        return True

    def thumbnail_file_name(self, path: bytes) -> bytes:
        """Compute the thumbnail file name
        See https://standards.freedesktop.org/thumbnail-spec/latest/x227.html
        """
        uri = self.get_uri(path)
        hash_ = md5(uri.encode("utf-8")).hexdigest()
        return bytestring_path(f"{hash_}.png")

    def add_tags(self, artpath: bytes, image_path: bytes) -> None:
        """Write required metadata to the thumbnail
        See https://standards.freedesktop.org/thumbnail-spec/latest/x142.html
        """
        mtime = os.stat(syspath(artpath)).st_mtime
        metadata = {
            "Thumb::URI": self.get_uri(artpath),
            "Thumb::MTime": str(mtime),
        }
        try:
            ArtResizer.shared.write_metadata(image_path, metadata)
        except Exception:
            self._log.exception(
                "could not write metadata to {}", displayable_path(image_path)
            )

    def make_dolphin_cover_thumbnail(
        self, album_path: bytes, artpath: bytes
    ) -> None:
        outfilename = os.path.join(album_path, b".directory")
        if os.path.exists(syspath(outfilename)):
            return
        artfile = os.path.split(artpath)[1]
        with open(syspath(outfilename), "w") as f:
            f.write("[Desktop Entry]\n")
            f.write(f"Icon=./{artfile.decode('utf-8')}")
            f.close()
        self._log.debug("Wrote file {}", displayable_path(outfilename))


class URIGetter:
    available = False
    name = "Abstract base"

    def uri(self, path: bytes) -> str:
        raise NotImplementedError()


class PathlibURI(URIGetter):
    available = True
    name = "Python Pathlib"

    def uri(self, path: bytes) -> str:
        return PurePosixPath(os.fsdecode(path)).as_uri()


def copy_c_string(c_string: Any) -> bytes | None:
    """Copy a `ctypes.POINTER(ctypes.c_char)` value into a new Python
    string and return it. The old memory is then safe to free.
    """
    # This is a pretty dumb way to get a string copy, but it seems to
    # work. A more surefire way would be to allocate a ctypes buffer and copy
    # the data with `memcpy` or somesuch.
    return ctypes.cast(c_string, ctypes.c_char_p).value


class GioURI(URIGetter):
    """Use gio URI function g_file_get_uri. Paths must be utf-8 encoded."""

    name = "GIO"

    def __init__(self) -> None:
        self.libgio = self.get_library()
        self.available = bool(self.libgio)
        if self.libgio:
            self.libgio.g_type_init()  # for glib < 2.36

            self.libgio.g_file_new_for_path.argtypes = [ctypes.c_char_p]
            self.libgio.g_file_new_for_path.restype = ctypes.c_void_p

            self.libgio.g_file_get_uri.argtypes = [ctypes.c_void_p]
            self.libgio.g_file_get_uri.restype = ctypes.POINTER(ctypes.c_char)

            self.libgio.g_object_unref.argtypes = [ctypes.c_void_p]

    def get_library(self) -> ctypes.CDLL | None:
        lib_name = ctypes.util.find_library("gio-2")
        try:
            if not lib_name:
                return None
            return ctypes.cdll.LoadLibrary(lib_name)
        except OSError:
            return None

    def uri(self, path: bytes) -> str:
        libgio = self.libgio
        if libgio is None:
            raise RuntimeError("GIO library is unavailable")

        g_file_ptr = libgio.g_file_new_for_path(path)
        if not g_file_ptr:
            raise RuntimeError(
                f"No gfile pointer received for {displayable_path(path)}"
            )

        try:
            uri_ptr = libgio.g_file_get_uri(g_file_ptr)
        finally:
            libgio.g_object_unref(g_file_ptr)
        if not uri_ptr:
            libgio.g_free(uri_ptr)
            raise RuntimeError(
                f"No URI received from the gfile pointer for {displayable_path(path)}"
            )

        try:
            uri = copy_c_string(uri_ptr)
        finally:
            libgio.g_free(uri_ptr)

        if uri is None:
            raise RuntimeError("GIO returned NULL for filename")

        try:
            return os.fsdecode(uri)
        except UnicodeDecodeError:
            raise RuntimeError(f"Could not decode filename from GIO: {uri!r}")
