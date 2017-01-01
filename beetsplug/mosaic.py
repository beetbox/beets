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
from __future__ import absolute_import, division, print_function

import math

import os.path

from random import shuffle

from PIL import Image

from beets import ui

from beets.plugins import BeetsPlugin

from parse import parse


# MOSAICFONT = os.path.join(os.path.dirname(__file__), 'FreeSans.ttf')


class MosaicCoverArtPlugin(BeetsPlugin):
    col_size = 4

    def __init__(self):
        super(MosaicCoverArtPlugin, self).__init__()

        self.config.add({'geometry': '100x100+3+3',
                         'tile': '',  # or e.g. x3 3x
                         'label': '',
                         'background': 'ffffff',
                         'mosaic': 'mosaic.png',
                         'show_mosaic': False,
                         'random': False,
                         'watermark': '',
                         'watermark_alpha': 0.4})

    def commands(self):
        cmd = ui.Subcommand('mosaic', help=u"create mosaic from coverart")

        cmd.parser.add_option(
            u'-r', u'--random',
            action='store_true',
            help=u'randomize cover art'
        )

        cmd.parser.add_option(
            u'-m', u'--mosaic', dest='mosaic',  metavar='FILE',
            action='store',
            help=u'save final mosaic picture as FILE'
        )

        cmd.parser.add_option(
            u'-w', u'--watermark', dest='watermark',
            action='store', metavar='FILE',
            help=u'add FILE for a picture to blend over mosaic'
        )

        cmd.parser.add_option(
            u'-a', u'--alpha', dest='watermark_alpha',
            action='store', metavar='ALPHA',
            help=u'ALPHA value for blending'
        )
        cmd.parser.add_option(
            u'-c', u'--color', dest='background',
            action='store', metavar='HEXCOLOR',
            help=u'background color as HEXCOLOR'
        )

        cmd.parser.add_option(
            u'-g', u'--geometry', dest='geometry',
            action='store', metavar='GEOMETRY',
            help=u'define geometry as <width>x<height>+<marginx>+<marginy>'
        )

        def func(lib, opts, args):
            self.config.set_args(opts)

            random = self.config['random']
            mosaic = self.config['mosaic'].as_str()
            watermark = self.config['watermark'].as_str()
            watermark_alpha = self.config['watermark_alpha'].get(float)
            background = self.config['background'].as_str()
            geometry = self.config['geometry'].as_str()

            albums = lib.albums(ui.decargs(args))

            self._generate_montage(lib,
                                   albums,
                                   mosaic,
                                   watermark,
                                   background,
                                   watermark_alpha,
                                   geometry,
                                   random)

        cmd.func = func
        return [cmd]

    def _generate_montage(self, lib, albums,
                          fn_mosaic, fn_watermark,
                          background, watermark_alpha, geometry, random):

        parsestr = "{cellwidth:d}x{cellheight:d}"
        parsestr += "+{cellmarginx:d}+{cellmarginy:d}"

        geo = parse(parsestr, geometry)
        covers = []

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

        if tail >= cols:
            cols += 1

        tail = len(covers) - (cols * sqrtnum)

        if tail > 0:
            rows += 1

        self._log.debug(u'Cells: {}x{}', cols, rows)

        mosaic_size_width = geo['cellmarginx'] + (cols * (geo['cellwidth'] +
                                                          geo['cellmarginx']))

        mosaic_size_height = geo['cellmarginy'] + (rows *
                                                   (geo['cellheight'] +
                                                    geo['cellmarginy']))

        self._log.debug(u'Mosaic size: {}x{}',
                        mosaic_size_width, mosaic_size_height)

        montage = Image.new('RGB', (mosaic_size_width, mosaic_size_height),
                            tuple(int(background[i:i + 2], 16)
                                  for i in (0, 2, 4)))

        size = int(geo['cellwidth']), int(geo['cellheight'])
        offset_x = int(geo['cellmarginx'])
        offset_y = int(geo['cellmarginy'])
        colcounter = 0

#        fnt = ImageFont.truetype(MOSAICFONT, 12)
        if random:
            shuffle(covers)
            self._log.debug(u'Randomize cover art')

        for cover in covers:

            try:
                if '||' in cover:

                    im = Image.new('RGB', size,
                                   tuple(int(background[i:i + 2], 16)
                                         for i in (0, 2, 4)))
                    self._log.info(u'Cover not available for {} ',
                                   cover[2:].replace('\n', '-'))
#                    d = ImageDraw.Draw(im)
#                    d.multiline_text((10, 10), cover[2:],
#                                     fill=(0, 0, 0), font=fnt, anchor=None,
#                                     spacing=0, align="left")

                else:
                    im = Image.open(cover)
                    im.thumbnail(size, Image.ANTIALIAS)

                self._log.debug(u'Paste into mosaic: {} - {}x{}',
                                cover, offset_x, offset_y)
                montage.paste(im, (offset_x, offset_y))

                colcounter += 1
                if colcounter >= cols:
                    offset_y += geo['cellwidth'] + geo['cellmarginy']
                    offset_x = geo['cellmarginx']
                    colcounter = 0
                else:
                    offset_x += geo['cellwidth'] + geo['cellmarginx']

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
