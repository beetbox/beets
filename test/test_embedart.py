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


class EmbedartCliTest(unittest.TestCase, TestHelper):

    artpath = os.path.join(_common.RSRC, 'image-2x3.jpg')

    def setUp(self):
        self.setup_beets()  # Converter is threaded
        self.load_plugins('embedart')
        with open(self.artpath) as f:
            self.image_data = f.read()

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_embed_art_from_file(self):
        album = self.add_album_fixture()
        item = album.items()[0]
        self.run_command('embedart', '-f', self.artpath)
        mediafile = MediaFile(item.path)
        self.assertEqual(mediafile.images[0].data, self.image_data)

    def test_embed_art_from_album(self):
        album = self.add_album_fixture()
        item = album.items()[0]

        album.artpath = self.artpath
        album.store()
        self.run_command('embedart')
        mediafile = MediaFile(item.path)
        self.assertEqual(mediafile.images[0].data, self.image_data)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
