# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Thomas Scholtes.
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


class FetchartCliTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()
        self.load_plugins('fetchart')
        self.config['fetchart']['cover_names'] = 'c\xc3\xb6ver.jpg'
        self.config['art_filename'] = 'mycover'
        self.album = self.add_album()

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_set_art_from_folder(self):
        self.touch(b'c\xc3\xb6ver.jpg', dir=self.album.path, content='IMAGE')

        self.run_command('fetchart')
        cover_path = os.path.join(self.album.path, b'mycover.jpg')

        self.album.load()
        self.assertEqual(self.album['artpath'], cover_path)
        with open(util.syspath(cover_path), 'r') as f:
            self.assertEqual(f.read(), 'IMAGE')

    def test_filesystem_does_not_pick_up_folder(self):
        os.makedirs(os.path.join(self.album.path, b'mycover.jpg'))
        self.run_command('fetchart')
        self.album.load()
        self.assertEqual(self.album['artpath'], None)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
