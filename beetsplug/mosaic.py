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
from PIL import Image

import math


class MosaicCoverArtPlugin(BeetsPlugin):
    col_size = 4
    margin = 3

    def __init__(self):
        super(MosaicCoverArtPlugin, self).__init__()
        self.config.add({'maxwidth': 300})
        self.maxwidth = self.config['maxwidth'].get(int)

    def commands(self):
        cmd = ui.Subcommand('mosaic', help=u"create mosaic from coverart")

        def func(lib, opts, args):
            self._generate_montage(lib,
                                   lib.albums(ui.decargs(args)), u'mos.png')

        cmd.func = func
        return [cmd]

    def _generate_montage(self, lib, albums, output_fn):

        covers = []

        for album in albums:

            if album.artpath and os.path.exists(album.artpath):
                self._log.info(u'#{}#', album.artpath)
                covers.append(album.artpath)
            else:
                self._log.info(u'#{} has no album?#', album)

        sqrtnum = int(math.sqrt(len(covers)))

        tail = len(covers) - (sqrtnum * sqrtnum)

        rows = cols = sqrtnum

        if tail > 0:
            cols += 1

        self._log.info(u'{}x{}', cols, rows)

        montage = Image.new(mode='RGB',
                            size=(cols * (100 + self.margin),
                                  rows * (100 + self.margin)),
                            color=(0, 0, 0, 0))

        size = 100, 100
        offset_x = 0
        offset_y = 0
        colcounter = 0
        for cover in covers:

            try:
                im = Image.open(cover)
                im.thumbnail(size, Image.ANTIALIAS)
                self._log.info(u'Paste into mosaic: {} - {}x{}',
                               cover, offset_x, offset_y)
                montage.paste(im, (offset_x, offset_y))

                colcounter += 1
                if colcounter >= cols:
                    offset_y += 100 + self.margin
                    offset_x = 0
                    colcounter = 0
                else:
                    offset_x += 100 + self.margin

                    im.close()
            except IOError:
                self._log.error(u'Problem with {}', cover)
        self._log.info(u'Save montage to: {}', output_fn)
        foreground = Image.open("c:/temp/tool.png")
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

        self._log.info(u'Save montage to: {}:{}-{} {}:{}-{}',
                       img5.mode, m_width, m_height, nf.mode,
                       f_width, f_height)
        Image.blend(img5, nf2, 0.4).save(output_fn)

        # montage.save(output_fn)
