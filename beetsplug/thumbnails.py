# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2015, Bruno Cauet
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

"""Create freedesktop.org-compliant thumnails for album folders

This plugin is POSIX-only.
Spec: standards.freedesktop.org/thumbnail-spec/latest/index.html
"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from hashlib import md5
import os
import shutil
from itertools import chain
from pathlib import PurePosixPath

from xdg import BaseDirectory

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, decargs
from beets import util
from beets.util.artresizer import ArtResizer, has_IM, has_PIL


BASE_DIR = os.path.join(BaseDirectory.xdg_cache_home, "thumbnails")
NORMAL_DIR = os.path.join(BASE_DIR, "normal")
LARGE_DIR = os.path.join(BASE_DIR, "large")


class ThumbnailsPlugin(BeetsPlugin):
    def __init__(self):
        super(ThumbnailsPlugin, self).__init__()
        self.config.add({
            'auto': True,
            'force': False,
            'dolphin': False,
        })

        self.write_metadata = None
        if self.config['auto'] and self._check_local_ok():
            self.register_listener('art_set', self.process_album)

    def commands(self):
        thumbnails_command = Subcommand("thumbnails",
                                        help="Create album thumbnails")
        thumbnails_command.parser.add_option(
            '-f', '--force', dest='force', action='store_true', default=False,
            help='force regeneration of thumbnails deemed fine (existing & '
                 'recent enough)')
        thumbnails_command.parser.add_option(
            '--dolphin', dest='dolphin', action='store_true', default=False,
            help="create Dolphin-compatible thumbnail information (for KDE)")
        thumbnails_command.func = self.process_query

        return [thumbnails_command]

    def process_query(self, lib, opts, args):
        self.config.set_args(opts)
        if self._check_local_ok():
            for album in lib.albums(decargs(args)):
                self.process_album(album)

    def _check_local_ok(self):
        """Check that's everythings ready:
            - local capability to resize images
            - thumbnail dirs exist (create them if needed)
            - detect whether we'll use PIL or IM
        """
        if not ArtResizer.shared.local:
            self._log.warning("No local image resizing capabilities, "
                              "cannot generate thumbnails")
            return False

        for dir in (NORMAL_DIR, LARGE_DIR):
            if not os.path.exists(dir):
                os.makedirs(dir)

        if has_IM():
            self.write_metadata = write_metadata_im
        else:
            assert has_PIL()  # since we're local
            self.write_metadata = write_metadata_pil

        return True

    def process_album(self, album):
        """Produce thumbnails for the album folder.
        """
        self._log.debug(u'generating thumbnail for {0}', album)
        if not album.artpath:
            self._log.info(u'album {0} has no art', album)
            return

        if self.config['dolphin']:
            self.make_dolphin_cover_thumbnail(album)

        size = ArtResizer.shared.get_size(album.artpath)
        if not size:
            self._log.warning('problem getting the picture size for {0}',
                              album.artpath)
            return

        wrote = True
        if max(size) >= 256:
            wrote &= self.make_cover_thumbnail(album, 256, LARGE_DIR)
        wrote &= self.make_cover_thumbnail(album, 128, NORMAL_DIR)

        if wrote:
            self._log.info('wrote thumbnail for {0}', album)
        else:
            self._log.info('nothing to do for {0}', album)

    def make_cover_thumbnail(self, album, size, target_dir):
        """Make a thumbnail of given size for `album` and put it in
        `target_dir`.
        """
        self._log.debug("building thumbnail to put on {0}", album.path)
        target = os.path.join(target_dir, self.thumbnail_file_name(album.path))

        if os.path.exists(target) and \
           os.stat(target).st_mtime > os.stat(album.artpath).st_mtime:
            if self.config['force']:
                self._log.debug("found a suitable thumbnail for {0}, "
                                "forcing regeneration", album)
            else:
                self._log.debug("thumbnail for {0} exists and is recent "
                                "enough", album)
                return False
        resized = ArtResizer.shared.resize(size, album.artpath,
                                           util.syspath(target))
        self.add_tags(album, util.syspath(resized))
        shutil.move(resized, target)
        return True

    @staticmethod
    def thumbnail_file_name(path):
        """Compute the thumbnail file name
        See http://standards.freedesktop.org/thumbnail-spec/latest/x227.html
        """
        uri = PurePosixPath(path).as_uri()
        hash = md5(uri).hexdigest()
        return "{0}.png".format(hash)

    def add_tags(self, album, image_path):
        """Write required metadata to the thumbnail
        See http://standards.freedesktop.org/thumbnail-spec/latest/x142.html
        """
        metadata = {"Thumb::URI": PurePosixPath(album.artpath).as_uri(),
                    "Thumb::MTime": unicode(os.stat(album.artpath).st_mtime)}
        try:
            self.write_metadata(image_path, metadata)
        except Exception:
            self._log.exception("could not write metadata to {0}",
                                util.displayable_path(image_path))

    def make_dolphin_cover_thumbnail(self, album):
        outfilename = os.path.join(album.path, b".directory")
        if os.path.exists(outfilename):
            return
        artfile = os.path.split(album.artpath)[1]
        with open(outfilename, 'w') as f:
            f.write(b"[Desktop Entry]\nIcon=./{0}".format(artfile))
            f.close()
        self._log.debug("Wrote file {0}", util.displayable_path(outfilename))


def write_metadata_im(file, metadata):
    """Enrich the file metadata with `metadata` dict thanks to IM."""
    command = ['convert', file] + \
        list(chain.from_iterable(('-set', k, v) for k, v in metadata.items())) + \
        [file]
    util.command_output(command)
    return True


def write_metadata_pil(file, metadata):
    """Enrich the file metadata with `metadata` dict thanks to PIL."""
    from PIL import Image, PngImagePlugin
    im = Image.open(file)
    meta = PngImagePlugin.PngInfo()
    for k, v in metadata.items():
        meta.add_text(k, v, 0)
    im.save(file, "PNG", pnginfo=meta)
    return True
