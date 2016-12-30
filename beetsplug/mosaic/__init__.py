# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2015-2016, Ohm Patel.
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
"""Allows beets to create a mosaic from covers."""
from __future__ import division, absolute_import, print_function

import os.path

from beets.plugins import BeetsPlugin
from beets import ui
from PIL import Image, ImageDraw, ImageFont

import math

MOSAICFONT = os.path.join(os.path.dirname(__file__), 'FreeSans.ttf')


class MosaicCoverArtPlugin(BeetsPlugin):
    col_size = 4
    margin = 3

    def __init__(self):
        super(MosaicCoverArtPlugin, self).__init__()

        self.config.add({'geometry': '',
                         'tile': '',  # or e.g. x3 3x
                         'label': '',
                         'background': 'ffffff',
                         'mosaic': 'mosaic.png',
                         'show_mosaic': False,
                         'watermark': '',
                         'watermark_alpha': 0.4})

    def commands(self):
        cmd = ui.Subcommand('mosaic', help=u"create mosaic from coverart")

        cmd.parser.add_option(
            u'-m', u'--mosaic', dest='mosaic',
            action='store_false', default=None,
            help=u'add filename for final mosaic picture - default: mosaic.png'
        )

        cmd.parser.add_option(
            u'-w', u'--watermark', dest='watermark',
            action='store_false', default=None,
            help=u'add filename for a picture to blend over mosaic'
        )

        cmd.parser.add_option(
            u'-a', u'--alpha', dest='watermark_alpha',
            action='store_false', default=None,
            help=u'alpha value for blending - default: 0.4'
        )
        cmd.parser.add_option(
            u'-c', u'--color', dest='background',
            action='store_false', default=None,
            help=u'background color - default: ffffff'
        )

        def func(lib, opts, args):
            self.config.set_args(opts)

            if self.config['mosaic']:
                mosaic = opts.mosaic or self.config['mosaic'].get(str)
            else:
                mosaic = opts.mosaic

            self._log.info(u'Mosaic: {}', mosaic)

            if self.config['watermark']:
                watermark = opts.watermark or self.config['watermark'].get(str)
            else:
                watermark = opts.watermark

            watermark_alpha = opts.watermark_alpha or self.config[
                'watermark_alpha'].get(float)

            if self.config['background']:
                background = opts.background or self.config[
                    'background'].get(str)
            else:
                background = opts.background

            albums = lib.albums(ui.decargs(args))

            self._generate_montage(lib,
                                   albums,
                                   mosaic,
                                   watermark,
                                   background,
                                   watermark_alpha)

        cmd.func = func
        return [cmd]

    def _generate_montage(self, lib, albums,
                          fn_mosaic, fn_watermark,
                          background, watermark_alpha):

        covers = []

        self._log.info(u'Scan available cover art ...')

        for album in albums:

            if album.artpath and os.path.exists(album.artpath):
                self._log.debug(u'{}', album.artpath)
                covers.append(album.artpath)
            else:
                covers.append("||" + album.albumartist + "\n" + album.album)
                self._log.debug(u'#{} has no album?#', album)

        sqrtnum = int(math.sqrt(len(covers)))

        tail = len(covers) - (sqrtnum * sqrtnum)

        rows = cols = sqrtnum

        if tail>=cols:
            cols += 1

        tail = len(covers) - (cols * sqrtnum)
        
        if tail > 0:
            rows += 1

        self._log.info(u'{}x{}', cols, rows)

        mosaic_size_width = self.margin + (cols * (100 + self.margin))
        mosaic_size_height = self.margin + (rows * (100 + self.margin))

        self._log.info(u'Mosaic size: {}x{}',
                       mosaic_size_width, mosaic_size_height)

        montage = Image.new('RGB', (mosaic_size_width, mosaic_size_height),
                            tuple(int(background[i:i + 2], 16)
                                  for i in (0, 2, 4)))

        size = 100, 100
        offset_x = self.margin
        offset_y = self.margin
        colcounter = 0

        fnt = ImageFont.truetype(MOSAICFONT, 12)

        for cover in covers:

            try:
                if '||' in cover:

                    im = Image.new('RGB', size,
                                   tuple(int(background[i:i + 2], 16)
                                         for i in (0, 2, 4)))
                    d = ImageDraw.Draw(im)
                    d.multiline_text((10, 10), cover[2:],
                                     fill=(0, 0, 0), font=fnt, anchor=None,
                                     spacing=0, align="left")

                else:
                    im = Image.open(cover)
                    im.thumbnail(size, Image.ANTIALIAS)

                self._log.debug(u'Paste into mosaic: {} - {}x{}',
                                cover, offset_x, offset_y)
                montage.paste(im, (offset_x, offset_y))

                colcounter += 1
                if colcounter >= cols:
                    offset_y += 100 + self.margin
                    offset_x = self.margin
                    colcounter = 0
                else:
                    offset_x += 100 + self.margin

                    im.close()
            except IOError:
                self._log.error(u'Problem with {}', cover)

        if fn_watermark:
            foreground = Image.open(fn_watermark)
            m_width, m_height = montage.size
            f_width, f_height = foreground.size

            if f_width > f_height:
                d = f_width / 2 - (f_height / 2)
                e = f_width / 2 + (f_height / 2)
                box = (d, 0, e, f_height)
                nf = foreground.crop(box)
            elif f_width < f_height:
                d = f_height / 2 - (f_width / 2)
                e = f_height / 2 + (f_width / 2)
                box = (0, d, f_width, e)
                nf = foreground.crop(box)
            else:
                nf = foreground

            longer_side = max(montage.size)
            horizontal_padding = (longer_side - montage.size[0]) / 2
            vertical_padding = (longer_side - montage.size[1]) / 2
            img5 = montage.crop(
                (
                    -horizontal_padding,
                    -vertical_padding,
                    montage.size[0] + horizontal_padding,
                    montage.size[1] + vertical_padding
                )
            )

            m_width, m_height = img5.size

            nf2 = nf.resize(img5.size, Image.ANTIALIAS)
            f_width, f_height = nf2.size

            self._log.debug(u'Save montage to: {}:{}-{} {}:{}-{}',
                            img5.mode, m_width, m_height, nf.mode,
                            f_width, f_height)
            Image.blend(img5, nf2, watermark_alpha).save(fn_mosaic)
        else:
            montage.save(fn_mosaic)
