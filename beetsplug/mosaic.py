# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2017 Susanna Maria Hepp
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

from PIL import Image, ImageDraw, ImageFont

from beets import ui

from beets.plugins import BeetsPlugin

from parse import parse

import requests


class MosaicCoverArtPlugin(BeetsPlugin):

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
                         'watermark_alpha': 0.4,
                         'font': 'https://github.com/google/fonts/raw/'
                                 'master/ofl/inconsolata/'
                                 'Inconsolata-Regular.ttf'})

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
            help=u'ALPHA value for blending',
            type="float"
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
        cmd.parser.add_option(
            u'-f', u'--font', dest='font',
            action='store', metavar='FONT',
            help=u'url of ttf-font'
        )

        def func(lib, opts, args):
            """collect parameters and download the font for cover creation
            if cover not available for album
            """
            self.config.set_args(opts)

            random = self.config['random']
            mosaic = self.config['mosaic'].as_str()
            watermark = self.config['watermark'].as_str()
            watermark_alpha = self.config['watermark_alpha'].get(float)
            background = self.config['background'].as_str()
            geometry = self.config['geometry'].as_str()
            fonturl = self.config['font'].as_str()

            albums = lib.albums(ui.decargs(args))
            filename = fonturl[fonturl.rfind("/") + 1:]
            fontpath = os.path.join(os.path.dirname(__file__), filename)

            if not os.path.isfile(fontpath):
                self._log.debug("Download Font: " + fonturl)
                response = requests.get(fonturl)
                with open(fontpath, 'wb') as f:
                    f.write(response.content)

            self._generate_montage(lib,
                                   albums,
                                   mosaic,
                                   watermark,
                                   background,
                                   watermark_alpha,
                                   geometry,
                                   random,
                                   fontpath)

        cmd.func = func
        return [cmd]

    def _insert_newlines(self, string, every=15):
        lines = []
        for i in range(0, len(string), every):
            lines.append(string[i:i + every])
        return '\n'.join(lines)

    def _generate_montage(self, lib, albums,
                          fn_mosaic, fn_watermark,
                          background, watermark_alpha,
                          geometry, random, fontpath):
        """Generate the mosaic.
        """
        # Construct the parser for getting the geometry parameter
        parsestr = "{cellwidth:d}x{cellheight:d}"
        parsestr += "+{cellmarginx:d}+{cellmarginy:d}"
        geo = parse(parsestr, geometry)

        # Load Truetype font from plugin folder, which was downloaded before
        # tweak the fontsize according to the cell width
        fnt = ImageFont.truetype(fontpath, int(round(geo['cellwidth'] / 10)))

        covers = []
        # based on retrieved albums create a list of album cover
        for album in albums:
            self._log.debug(u'{}', album.artpath)
            if album.artpath and os.path.exists(album.artpath):
                self._log.debug(u'{}', album.artpath)
                covers.append(album.artpath)
            else:
                # if album cover not present use the albumartist and album
                # which will be used later for cover creation
                covers.append("||" + album.albumartist + "\n" + album.album)
                self._log.debug(u'#{} has no album?#', album)

        # calculate the number of rows and cols of the final mosaic
        # try to achieve a square size
        sqrtnum = int(math.sqrt(len(covers)))

        tail = len(covers) - (sqrtnum * sqrtnum)
        rows = cols = sqrtnum

        if tail >= cols:
            cols += 1

        tail = len(covers) - (cols * sqrtnum)

        if tail > 0:
            rows += 1

        self._log.debug(u'Cells: {}x{}', cols, rows)

        # calculate the final mosaix size in pixel
        mosaic_size_width = geo['cellmarginx'] + (cols * (geo['cellwidth'] +
                                                          geo['cellmarginx']))

        mosaic_size_height = geo['cellmarginy'] + (rows *
                                                   (geo['cellheight'] +
                                                    geo['cellmarginy']))

        self._log.debug(u'Mosaic size: {}x{}',
                        mosaic_size_width, mosaic_size_height)
        # Create the mosiac image
        montage = Image.new('RGB', (mosaic_size_width, mosaic_size_height),
                            tuple(int(background[i:i + 2], 16)
                                  for i in (0, 2, 4)))

        size = int(geo['cellwidth']), int(geo['cellheight'])
        offset_x = int(geo['cellmarginx'])
        offset_y = int(geo['cellmarginy'])
        colcounter = 0

        # shuffle the list of covers if desired
        if random:
            shuffle(covers)
            self._log.debug(u'Randomize cover art')

        for cover in covers:
            try:
                if '||' in str(cover):
                    info = cover[2:].strip()
                    # I faced the problem with entries
                    # in the database with empty album and artist
                    # this is for robustness
                    if not info:
                        continue
                    im = Image.new('RGB', size,
                                   tuple(int(background[i:i + 2], 16)
                                         for i in (0, 2, 4)))
                    self._log.debug(u'Cover not available for {} ',
                                    info.replace('\n', '-'))
                    d = ImageDraw.Draw(im)
                    info = self._insert_newlines(info.replace('\n', '-'))
                    # Using text to identify the missing cover in the mosic
                    d.multiline_text((int(round(geo['cellwidth'] / 10)), int(
                        round(geo['cellheight'] / 10))), info,
                        font=fnt, fill=(255, 0, 0, 255))
                else:
                    # load the normal cover image
                    # and resize it
                    im = Image.open(cover)
                    im.thumbnail(size, Image.ANTIALIAS)

                self._log.debug(u'Paste into mosaic: {} - {}x{}',
                                cover, offset_x, offset_y)
                # Paste the image at the right position in the mosaic
                montage.paste(im, (offset_x, offset_y))

                # Increase the counter for the column, used for
                # calculation of the postion of the next cover in the mosaic
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
            # Load the watermark image
            foreground = Image.open(fn_watermark)
            m_width, m_height = montage.size
            f_width, f_height = foreground.size

            # Calculate the final size of the watermark picture
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
            # Crop the watermark picture that the ratio fits to the
            # mosaic
            img5 = montage.crop(
                (
                    -horizontal_padding,
                    -vertical_padding,
                    montage.size[0] + horizontal_padding,
                    montage.size[1] + vertical_padding
                )
            )

            m_width, m_height = img5.size
            # Resize the watermark picture finally
            nf2 = nf.resize(img5.size, Image.ANTIALIAS)
            f_width, f_height = nf2.size

            self._log.debug(u'Save montage to: {}:{}-{} {}:{}-{}',
                            img5.mode, m_width, m_height, nf.mode,
                            f_width, f_height)
            # Blend the watermark with the mosaic together
            Image.blend(img5, nf2, watermark_alpha).save(fn_mosaic)
        else:
            montage.save(fn_mosaic)
