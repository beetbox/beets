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

"""High-level utilities for manipulating image files associated with
music and items' embedded album art.
"""

import subprocess
import platform
from tempfile import NamedTemporaryFile
import imghdr
import os

from beets.util import displayable_path, syspath
from beets.util.artresizer import ArtResizer
from beets import mediafile


def mediafile_image(image_path, maxwidth=None):
    """Return a `mediafile.Image` object for the path.
    """

    with open(syspath(image_path), 'rb') as f:
        data = f.read()
    return mediafile.Image(data, type=mediafile.ImageType.front)


def get_art(log, item):
    # Extract the art.
    try:
        mf = mediafile.MediaFile(syspath(item.path))
    except mediafile.UnreadableFileError as exc:
        log.warning(u'Could not extract art from {0}: {1}',
                    displayable_path(item.path), exc)
        return

    return mf.art


def embed_item(log, item, imagepath, maxwidth=None, itempath=None,
               compare_threshold=0, ifempty=False, as_album=False):
    """Embed an image into the item's media file.
    """
    # Conditions and filters.
    if compare_threshold:
        if not check_art_similarity(log, item, imagepath, compare_threshold):
            log.info(u'Image not similar; skipping.')
            return
    if ifempty and get_art(log, item):
            log.info(u'media file already contained art')
            return
    if maxwidth and not as_album:
        imagepath = resize_image(log, imagepath, maxwidth)

    # Get the `Image` object from the file.
    try:
        log.debug(u'embedding {0}', displayable_path(imagepath))
        image = mediafile_image(imagepath, maxwidth)
    except IOError as exc:
        log.warning(u'could not read image file: {0}', exc)
        return

    # Make sure the image kind is safe (some formats only support PNG
    # and JPEG).
    if image.mime_type not in ('image/jpeg', 'image/png'):
        log.info('not embedding image of unsupported type: {}',
                 image.mime_type)
        return

    item.try_write(path=itempath, tags={'images': [image]})


def embed_album(log, album, maxwidth=None, quiet=False,
                compare_threshold=0, ifempty=False):
    """Embed album art into all of the album's items.
    """
    imagepath = album.artpath
    if not imagepath:
        log.info(u'No album art present for {0}', album)
        return
    if not os.path.isfile(syspath(imagepath)):
        log.info(u'Album art not found at {0} for {1}',
                 displayable_path(imagepath), album)
        return
    if maxwidth:
        imagepath = resize_image(log, imagepath, maxwidth)

    log.info(u'Embedding album art into {0}', album)

    for item in album.items():
        embed_item(log, item, imagepath, maxwidth, None,
                   compare_threshold, ifempty, as_album=True)


def resize_image(log, imagepath, maxwidth):
    """Returns path to an image resized to maxwidth.
    """
    log.debug(u'Resizing album art to {0} pixels wide', maxwidth)
    imagepath = ArtResizer.shared.resize(maxwidth, syspath(imagepath))
    return imagepath


def check_art_similarity(log, item, imagepath, compare_threshold):
    """A boolean indicating if an image is similar to embedded item art.
    """
    with NamedTemporaryFile(delete=True) as f:
        art = extract(log, f.name, item)

        if art:
            is_windows = platform.system() == "Windows"

            # Converting images to grayscale tends to minimize the weight
            # of colors in the diff score.
            convert_proc = subprocess.Popen(
                [b'convert', syspath(imagepath), syspath(art),
                 b'-colorspace', b'gray', b'MIFF:-'],
                stdout=subprocess.PIPE,
                close_fds=not is_windows,
            )
            compare_proc = subprocess.Popen(
                [b'compare', b'-metric', b'PHASH', b'-', b'null:'],
                stdin=convert_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=not is_windows,
            )
            convert_proc.stdout.close()

            stdout, stderr = compare_proc.communicate()
            if compare_proc.returncode:
                if compare_proc.returncode != 1:
                    log.debug(u'IM phashes compare failed for {0}, {1}',
                              displayable_path(imagepath),
                              displayable_path(art))
                    return
                out_str = stderr
            else:
                out_str = stdout

            try:
                phash_diff = float(out_str)
            except ValueError:
                log.debug(u'IM output is not a number: {0!r}', out_str)
                return

            log.debug(u'compare PHASH score is {0}', phash_diff)
            return phash_diff <= compare_threshold

    return True


def extract(log, outpath, item):
    art = get_art(log, item)

    if not art:
        log.info(u'No album art present in {0}, skipping.', item)
        return

    # Add an extension to the filename.
    ext = imghdr.what(None, h=art)
    if not ext:
        log.warning(u'Unknown image type in {0}.',
                    displayable_path(item.path))
        return
    outpath += b'.' + ext

    log.info(u'Extracting album art from: {0} to: {1}',
             item, displayable_path(outpath))
    with open(syspath(outpath), 'wb') as f:
        f.write(art)
    return outpath


def extract_first(log, outpath, items):
    for item in items:
        real_path = extract(log, outpath, item)
        if real_path:
            return real_path


def clear(log, lib, query):
    items = lib.items(query)
    log.info(u'Clearing album art from {0} items', len(items))
    for item in items:
        log.debug(u'Clearing art for {0}', item)
        item.try_write(tags={'images': None})
