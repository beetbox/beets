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
from test.helper import TestHelper
from beets import util


class MosaicCliTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()
        self.load_plugins('mosaic')
        self.config['mosaic']['geometry'] = '150x150+3+3'
        self.config['mosaic']['mosaic'] = 'test_mosaic.png'
        self._set_up_data()

    def _set_up_data(self):
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

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_generate_mosaic(self):
        out = self.run_with_output('mosaic', '')

        self.assertIn('itunes_rating: 60 -> 80', out)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
