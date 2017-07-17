# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2017, Susanna Maria Hepp.
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

from __future__ import division, absolute_import, print_function

import os
import unittest
from test import _common
from test.helper import TestHelper
import tempfile
from beets.library import Item
from PIL import Image


MOSAIC_FILE = tempfile.NamedTemporaryFile(suffix='.png')


class MosaicCliTest(_common.TestCase, TestHelper):

    m1_artpath = os.path.join(_common.RSRC, b'mosaic_1.png')
    m2_artpath = os.path.join(_common.RSRC, b'mosaic_2.tif')
    m3_artpath = os.path.join(_common.RSRC, b'mosaic_3.jpg')

    def setUp(self):
        self.setup_beets()
        self.load_plugins('mosaic')
        self.config['mosaic']['geometry'] = '150x150+3+3'
        self.config['mosaic']['mosaic'] = MOSAIC_FILE.name

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_generate_mosaic_with_invalid(self):

        album_invalid = Item(
            albumartist=u'Artist A info',
            album=u'Album A info',
            path='',
            artpath="a/b/c/d/e.png"
        )
        self.lib.add_album([album_invalid])
        album_invalid = Item(
            albumartist=u'Artist B info',
            album=u'Album B info',
            path='',
            artpath="a/b/c/d/e.png"
        )
        self.lib.add_album([album_invalid])
        album_invalid = Item(
            albumartist=u'Artist C info',
            album=u'Album C info',
            path='',
            artpath="a/b/c/d/e.png"
        )
        self.lib.add_album([album_invalid])
        album_invalid = Item(
            albumartist=u'Artist D info',
            album=u'Album D info',
            path='',
            artpath="a/b/c/d/e.png"
        )
        self.lib.add_album([album_invalid])

        MOSAIC_FILE.close()
        self.run_with_output('mosaic', '')
        width = 0
        height = 0
        with Image.open(MOSAIC_FILE.name) as img:
            width, height = img.size
            del img

        os.remove(MOSAIC_FILE.name)
        self.assertEqual(width, 309)
        self.assertEqual(height, 309)

    def test_generate_mosaic_with_images(self):

        self.config['mosaic']['watermark'] = self.m3_artpath.decode("utf-8")

        album_invalid = Item(
            albumartist=u'Artist E info',
            album=u'Album A info',
            path='',
            artpath=self.m1_artpath.decode("utf-8")
        )
        self.lib.add_album([album_invalid])
        album_invalid = Item(
            albumartist=u'Artist F info',
            album=u'Album B info',
            path='',
            artpath=self.m2_artpath.decode("utf-8")
        )
        self.lib.add_album([album_invalid])
        album_invalid = Item(
            albumartist=u'Artist G info',
            album=u'Album C info',
            path='',
            artpath=self.m3_artpath.decode("utf-8")
        )
        self.lib.add_album([album_invalid])
        album_invalid = Item(
            albumartist=u'Artist H info',
            album=u'Album D info',
            path='',
            artpath=self.m1_artpath.decode("utf-8")
        )
        self.lib.add_album([album_invalid])

        MOSAIC_FILE.close()
        self.run_with_output('mosaic', '')
        width = 0
        height = 0
        with Image.open(MOSAIC_FILE.name) as img:
            width, height = img.size
            del img

        os.remove(MOSAIC_FILE.name)
        self.assertEqual(width, 309)
        self.assertEqual(height, 309)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
