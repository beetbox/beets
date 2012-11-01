# This file is part of beets.
# Copyright 2012, Fabrice Laporte
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
import urllib
import subprocess
import os
import glob
import shutil
from tempfile import NamedTemporaryFile
import logging

# Resizing methods
PIL = 1
IMAGEMAGICK = 2
WEBPROXY = 3

log = logging.getLogger('beets')


class ArtResizerError(Exception):
    """Raised when an error occurs during image resizing.
    """


def call(args):
    """Execute the command indicated by `args` (a list of strings) and
    return the command's output. The stderr stream is ignored. If the
    command exits abnormally, a ArtResizerError is raised.
    """
    try:
        with open(os.devnull, 'w') as devnull:
            return subprocess.check_output(args, stderr=devnull)
    except subprocess.CalledProcessError as e:
        raise ArtResizerError(
            "{0} exited with status {1}".format(args[0], e.returncode)
        )


def resize_url(url, maxwidth):
    """Return a new url with image of original url resized to maxwidth (keep 
       aspect ratio)"""

    PROXY_URL = 'http://images.weserv.nl/?url=%s&w=%s'
    reqUrl = PROXY_URL % (url.replace('http://',''), maxwidth)
    log.debug("Requesting proxy image at %s" % reqUrl)
    try:
        urllib.urlopen(reqUrl)
    except IOError:
        log.info('Cannot get resized image via web proxy. '
                 'Using original image url.')
        return url
    return reqUrl


def get_temp_file_out(path_in):
    """Return an unused filename with correct extension.
    """
    with NamedTemporaryFile(suffix=os.path.splitext(path_in)[1]) as f:
        path_out = f.name
    return path_out


class PilResizer(object):
    def resize(self, maxwidth, path_in, path_out=None) :
        """Resize using Python Imaging Library (PIL).  Return the output path 
        of resized image.
        """
        if not path_out:
            path_out = get_temp_file_out(path_in)
        try:
            im = Image.open(path_in)
            size = maxwidth, maxwidth
            im.thumbnail(size, Image.ANTIALIAS)
            im.save(path_out)
            return path_out
        except IOError:
            log.error("Cannot create thumbnail for '%s'" % path)


class ImageMagickResizer(object):
    def resize(self, maxwidth, path_in, path_out=None):
        """Resize using ImageMagick <http://www.imagemagick.org> command-line 
        tool. Return the output path of resized image.
        """
        if not path_out:
            path_out = get_temp_file_out(path_in)

        # widthxheight> Shrinks images with dimension(s) larger than the 
        # corresponding width and/or height dimension(s).
        # "only shrink flag" is prefixed by ^ escape char for Windows compat.
        cmd = [self.convert_path, path_in, '-resize', '%sx^>' % \
               maxwidth, path_out]
        call(cmd)
        return path_out


class ArtResizer(object):
    """A singleton class that performs image resizes.
    """
    convert_path = None 

    def __init__(self, detect=True):
        """ArtResizer factory method"""

        self.method = WEBPROXY
        if detect:
            self.method = self.set_method()

            if self.method == PIL :
                self.__class__ = PilResizer
            elif self.method == IMAGEMAGICK :
                self.__class__ = ImageMagickResizer
            log.debug("ArtResizer method is %s" % self.__class__)        

    def set_method(self):
        """Set the most appropriate resize method. Use PIL if present, else 
        check if ImageMagick is installed.
        If none is available, use a web proxy."""

        try:
            from PIL import Image
            return PIL
        except ImportError as e:
            pass

        for dir in os.environ['PATH'].split(os.pathsep):
            if glob.glob(os.path.join(dir, 'convert*')):
                convert = os.path.join(dir, 'convert')
                cmd = [convert, '--version']
                try:
                    out = subprocess.check_output(cmd).lower()
                    if 'imagemagick' in out:
                        self.convert_path = convert  
                        return IMAGEMAGICK
                except subprocess.CalledProcessError as e:
                    pass # system32/convert.exe may be interfering 

        return WEBPROXY

    def resize(self, maxwidth, url, path_out=None):
        """Resize using web proxy. Return the output path of resized image.
        """

        reqUrl = resize_url(url, maxwidth)
        try:
            fn, headers = urllib.urlretrieve(reqUrl)
        except IOError:
            log.debug('error fetching resized image')
            return

        if not path_out:
            path_out = get_temp_file_out(fn)
        shutil.copy(fn, path_out)
        return path_out


# Singleton instantiation.
inst = ArtResizer()
