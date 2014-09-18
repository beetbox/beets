# This file is part of beets.
# Copyright 2014, Thomas Scholtes.
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

import os.path
import _common
from _common import unittest
from helper import TestHelper

from beets.mediafile import MediaFile
from beets import config
from beets.util import syspath


class EmbedartCliTest(unittest.TestCase, TestHelper):

    small_artpath = os.path.join(_common.RSRC, 'image-2x3.jpg')
    abbey_artpath = os.path.join(_common.RSRC, 'abbey.jpg')
    abbey_similarpath = os.path.join(_common.RSRC, 'abbey-similar.jpg')
    abbey_differentpath = os.path.join(_common.RSRC, 'abbey-different.jpg')

    def setUp(self):
        self.setup_beets()  # Converter is threaded
        self.load_plugins('embedart')

    def _setup_data(self, artpath=None):
        if not artpath:
            artpath = self.small_artpath
        with open(syspath(artpath)) as f:
            self.image_data = f.read()

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_embed_art_from_file(self):
        self._setup_data()
        album = self.add_album_fixture()
        item = album.items()[0]
        self.run_command('embedart', '-f', self.small_artpath)
        mediafile = MediaFile(syspath(item.path))
        self.assertEqual(mediafile.images[0].data, self.image_data)

    def test_embed_art_from_album(self):
        self._setup_data()
        album = self.add_album_fixture()
        item = album.items()[0]
        album.artpath = self.small_artpath
        album.store()
        self.run_command('embedart')
        mediafile = MediaFile(syspath(item.path))
        self.assertEqual(mediafile.images[0].data, self.image_data)

    def test_reject_different_art(self):
        self._setup_data(self.abbey_artpath)
        album = self.add_album_fixture()
        item = album.items()[0]
        self.run_command('embedart', '-f', self.abbey_artpath)
        config['embedart']['compare_threshold'] = 20
        self.run_command('embedart', '-f', self.abbey_differentpath)
        mediafile = MediaFile(syspath(item.path))

        self.assertEqual(mediafile.images[0].data, self.image_data,
                         'Image written is not {0}'.format(
                         self.abbey_artpath))

    def test_accept_similar_art(self):
        self._setup_data(self.abbey_similarpath)
        album = self.add_album_fixture()
        item = album.items()[0]
        self.run_command('embedart', '-f', self.abbey_artpath)
        config['embedart']['compare_threshold'] = 20
        self.run_command('embedart', '-f', self.abbey_similarpath)
        mediafile = MediaFile(syspath(item.path))

        self.assertEqual(mediafile.images[0].data, self.image_data,
                         'Image written is not {0}'.format(
                         self.abbey_similarpath))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
