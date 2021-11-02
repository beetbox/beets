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

import subprocess
import os
import os.path
import re
from tempfile import NamedTemporaryFile
from urllib.parse import urlencode
from beets import logging
from beets import util

# Resizing methods
PIL = 1
IMAGEMAGICK = 2
WEBPROXY = 3

PROXY_URL = 'https://images.weserv.nl/'

log = logging.getLogger('beets')


def resize_url(url, maxwidth, quality=0):
    """Return a proxied image URL that resizes the original image to
    maxwidth (preserving aspect ratio).
    """
    params = {
        'url': url.replace('http://', ''),
        'w': maxwidth,
    }

    if quality > 0:
        params['q'] = quality

    return '{}?{}'.format(PROXY_URL, urlencode(params))


def temp_file_for(path):
    """Return an unused filename with the same extension as the
    specified path.
    """
    ext = os.path.splitext(path)[1]
    with NamedTemporaryFile(suffix=util.py3_path(ext), delete=False) as f:
        return util.bytestring_path(f.name)


def pil_resize(maxwidth, path_in, path_out=None, quality=0, max_filesize=0):
    """Resize using Python Imaging Library (PIL).  Return the output path
    of resized image.
    """
    path_out = path_out or temp_file_for(path_in)
    from PIL import Image

    log.debug('artresizer: PIL resizing {0} to {1}',
              util.displayable_path(path_in), util.displayable_path(path_out))

    try:
        im = Image.open(util.syspath(path_in))
        size = maxwidth, maxwidth
        im.thumbnail(size, Image.ANTIALIAS)

        if quality == 0:
            # Use PIL's default quality.
            quality = -1

        # progressive=False only affects JPEGs and is the default,
        # but we include it here for explicitness.
        im.save(util.py3_path(path_out), quality=quality, progressive=False)

        if max_filesize > 0:
            # If maximum filesize is set, we attempt to lower the quality of
            # jpeg conversion by a proportional amount, up to 3 attempts
            # First, set the maximum quality to either provided, or 95
            if quality > 0:
                lower_qual = quality
            else:
                lower_qual = 95
            for i in range(5):
                # 5 attempts is an abitrary choice
                filesize = os.stat(util.syspath(path_out)).st_size
                log.debug("PIL Pass {0} : Output size: {1}B", i, filesize)
                if filesize <= max_filesize:
                    return path_out
                # The relationship between filesize & quality will be
                # image dependent.
                lower_qual -= 10
                # Restrict quality dropping below 10
                if lower_qual < 10:
                    lower_qual = 10
                # Use optimize flag to improve filesize decrease
                im.save(util.py3_path(path_out), quality=lower_qual,
                        optimize=True, progressive=False)
            log.warning("PIL Failed to resize file to below {0}B",
                        max_filesize)
            return path_out

        else:
            return path_out
    except OSError:
        log.error("PIL cannot create thumbnail for '{0}'",
                  util.displayable_path(path_in))
        return path_in


def im_resize(maxwidth, path_in, path_out=None, quality=0, max_filesize=0):
    """Resize using ImageMagick.

    Use the ``magick`` program or ``convert`` on older versions. Return
    the output path of resized image.
    """
    path_out = path_out or temp_file_for(path_in)
    log.debug('artresizer: ImageMagick resizing {0} to {1}',
              util.displayable_path(path_in), util.displayable_path(path_out))

    # "-resize WIDTHx>" shrinks images with the width larger
    # than the given width while maintaining the aspect ratio
    # with regards to the height.
    # ImageMagick already seems to default to no interlace, but we include it
    # here for the sake of explicitness.
    cmd = ArtResizer.shared.im_convert_cmd + [
        util.syspath(path_in, prefix=False),
        '-resize', f'{maxwidth}x>',
        '-interlace', 'none',
    ]

    if quality > 0:
        cmd += ['-quality', f'{quality}']

    # "-define jpeg:extent=SIZEb" sets the target filesize for imagemagick to
    # SIZE in bytes.
    if max_filesize > 0:
        cmd += ['-define', f'jpeg:extent={max_filesize}b']

    cmd.append(util.syspath(path_out, prefix=False))

    try:
        util.command_output(cmd)
    except subprocess.CalledProcessError:
        log.warning('artresizer: IM convert failed for {0}',
                    util.displayable_path(path_in))
        return path_in

    return path_out


BACKEND_FUNCS = {
    PIL: pil_resize,
    IMAGEMAGICK: im_resize,
}


def pil_getsize(path_in):
    from PIL import Image

    try:
        im = Image.open(util.syspath(path_in))
        return im.size
    except OSError as exc:
        log.error("PIL could not read file {}: {}",
                  util.displayable_path(path_in), exc)


def im_getsize(path_in):
    cmd = ArtResizer.shared.im_identify_cmd + \
        ['-format', '%w %h', util.syspath(path_in, prefix=False)]

    try:
        out = util.command_output(cmd).stdout
    except subprocess.CalledProcessError as exc:
        log.warning('ImageMagick size query failed')
        log.debug(
            '`convert` exited with (status {}) when '
            'getting size with command {}:\n{}',
            exc.returncode, cmd, exc.output.strip()
        )
        return
    try:
        return tuple(map(int, out.split(b' ')))
    except IndexError:
        log.warning('Could not understand IM output: {0!r}', out)


BACKEND_GET_SIZE = {
    PIL: pil_getsize,
    IMAGEMAGICK: im_getsize,
}


def pil_deinterlace(path_in, path_out=None):
    path_out = path_out or temp_file_for(path_in)
    from PIL import Image

    try:
        im = Image.open(util.syspath(path_in))
        im.save(util.py3_path(path_out), progressive=False)
        return path_out
    except IOError:
        return path_in


def im_deinterlace(path_in, path_out=None):
    path_out = path_out or temp_file_for(path_in)

    cmd = ArtResizer.shared.im_convert_cmd + [
        util.syspath(path_in, prefix=False),
        '-interlace', 'none',
        util.syspath(path_out, prefix=False),
    ]

    try:
        util.command_output(cmd)
        return path_out
    except subprocess.CalledProcessError:
        return path_in


DEINTERLACE_FUNCS = {
    PIL: pil_deinterlace,
    IMAGEMAGICK: im_deinterlace,
}


def im_get_format(filepath):
    cmd = ArtResizer.shared.im_identify_cmd + [
        '-format', '%[magick]',
        util.syspath(filepath)
    ]

    try:
        return util.command_output(cmd).stdout
    except subprocess.CalledProcessError:
        return None


def pil_get_format(filepath):
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(util.syspath(filepath)) as im:
            return im.format
    except (ValueError, TypeError, UnidentifiedImageError, FileNotFoundError):
        log.exception("failed to detect image format for {}", filepath)
        return None


BACKEND_GET_FORMAT = {
    PIL: pil_get_format,
    IMAGEMAGICK: im_get_format,
}


def im_convert_format(source, target, deinterlaced):
    cmd = ArtResizer.shared.im_convert_cmd + [
        util.syspath(source),
        *(["-interlace", "none"] if deinterlaced else []),
        util.syspath(target),
    ]

    try:
        subprocess.check_call(
            cmd,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL
        )
        return target
    except subprocess.CalledProcessError:
        return source


def pil_convert_format(source, target, deinterlaced):
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(util.syspath(source)) as im:
            im.save(util.py3_path(target), progressive=not deinterlaced)
            return target
    except (ValueError, TypeError, UnidentifiedImageError, FileNotFoundError,
            OSError):
        log.exception("failed to convert image {} -> {}", source, target)
        return source


BACKEND_CONVERT_IMAGE_FORMAT = {
    PIL: pil_convert_format,
    IMAGEMAGICK: im_convert_format,
}


class Shareable(type):
    """A pseudo-singleton metaclass that allows both shared and
    non-shared instances. The ``MyClass.shared`` property holds a
    lazily-created shared instance of ``MyClass`` while calling
    ``MyClass()`` to construct a new object works as usual.
    """

    def __init__(cls, name, bases, dict):
        super().__init__(name, bases, dict)
        cls._instance = None

    @property
    def shared(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class ArtResizer(metaclass=Shareable):
    """A singleton class that performs image resizes.
    """

    def __init__(self):
        """Create a resizer object with an inferred method.
        """
        self.method = self._check_method()
        log.debug("artresizer: method is {0}", self.method)
        self.can_compare = self._can_compare()

        # Use ImageMagick's magick binary when it's available. If it's
        # not, fall back to the older, separate convert and identify
        # commands.
        if self.method[0] == IMAGEMAGICK:
            self.im_legacy = self.method[2]
            if self.im_legacy:
                self.im_convert_cmd = ['convert']
                self.im_identify_cmd = ['identify']
            else:
                self.im_convert_cmd = ['magick']
                self.im_identify_cmd = ['magick', 'identify']

    def resize(
        self, maxwidth, path_in, path_out=None, quality=0, max_filesize=0
    ):
        """Manipulate an image file according to the method, returning a
        new path. For PIL or IMAGEMAGIC methods, resizes the image to a
        temporary file and encodes with the specified quality level.
        For WEBPROXY, returns `path_in` unmodified.
        """
        if self.local:
            func = BACKEND_FUNCS[self.method[0]]
            return func(maxwidth, path_in, path_out,
                        quality=quality, max_filesize=max_filesize)
        else:
            return path_in

    def deinterlace(self, path_in, path_out=None):
        if self.local:
            func = DEINTERLACE_FUNCS[self.method[0]]
            return func(path_in, path_out)
        else:
            return path_in

    def proxy_url(self, maxwidth, url, quality=0):
        """Modifies an image URL according the method, returning a new
        URL. For WEBPROXY, a URL on the proxy server is returned.
        Otherwise, the URL is returned unmodified.
        """
        if self.local:
            return url
        else:
            return resize_url(url, maxwidth, quality)

    @property
    def local(self):
        """A boolean indicating whether the resizing method is performed
        locally (i.e., PIL or ImageMagick).
        """
        return self.method[0] in BACKEND_FUNCS

    def get_size(self, path_in):
        """Return the size of an image file as an int couple (width, height)
        in pixels.

        Only available locally.
        """
        if self.local:
            func = BACKEND_GET_SIZE[self.method[0]]
            return func(path_in)

    def get_format(self, path_in):
        """Returns the format of the image as a string.

        Only available locally.
        """
        if self.local:
            func = BACKEND_GET_FORMAT[self.method[0]]
            return func(path_in)

    def reformat(self, path_in, new_format, deinterlaced=True):
        """Converts image to desired format, updating its extension, but
        keeping the same filename.

        Only available locally.
        """
        if not self.local:
            return path_in

        new_format = new_format.lower()
        # A nonexhaustive map of image "types" to extensions overrides
        new_format = {
            'jpeg': 'jpg',
        }.get(new_format, new_format)

        fname, ext = os.path.splitext(path_in)
        path_new = fname + b'.' + new_format.encode('utf8')
        func = BACKEND_CONVERT_IMAGE_FORMAT[self.method[0]]

        # allows the exception to propagate, while still making sure a changed
        # file path was removed
        result_path = path_in
        try:
            result_path = func(path_in, path_new, deinterlaced)
        finally:
            if result_path != path_in:
                os.unlink(path_in)
        return result_path

    def _can_compare(self):
        """A boolean indicating whether image comparison is available"""

        return self.method[0] == IMAGEMAGICK and self.method[1] > (6, 8, 7)

    @staticmethod
    def _check_method():
        """Return a tuple indicating an available method and its version.

        The result has at least two elements:
        - The method, eitehr WEBPROXY, PIL, or IMAGEMAGICK.
        - The version.

        If the method is IMAGEMAGICK, there is also a third element: a
        bool flag indicating whether to use the `magick` binary or
        legacy single-purpose executables (`convert`, `identify`, etc.)
        """
        version = get_im_version()
        if version:
            version, legacy = version
            return IMAGEMAGICK, version, legacy

        version = get_pil_version()
        if version:
            return PIL, version

        return WEBPROXY, (0)


def get_im_version():
    """Get the ImageMagick version and legacy flag as a pair. Or return
    None if ImageMagick is not available.
    """
    for cmd_name, legacy in ((['magick'], False), (['convert'], True)):
        cmd = cmd_name + ['--version']

        try:
            out = util.command_output(cmd).stdout
        except (subprocess.CalledProcessError, OSError) as exc:
            log.debug('ImageMagick version check failed: {}', exc)
        else:
            if b'imagemagick' in out.lower():
                pattern = br".+ (\d+)\.(\d+)\.(\d+).*"
                match = re.search(pattern, out)
                if match:
                    version = (int(match.group(1)),
                               int(match.group(2)),
                               int(match.group(3)))
                    return version, legacy

    return None


def get_pil_version():
    """Get the PIL/Pillow version, or None if it is unavailable.
    """
    try:
        __import__('PIL', fromlist=['Image'])
        return (0,)
    except ImportError:
        return None
