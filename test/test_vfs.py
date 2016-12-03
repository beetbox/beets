# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Tests for the virtual filesystem builder.."""
from __future__ import division, absolute_import, print_function

import unittest
from test import _common
from beets import library
from beets import vfs


class VFSTest(_common.TestCase):
    def setUp(self):
        super(VFSTest, self).setUp()
        self.lib = library.Library(':memory:', path_formats=[
            (u'default', u'albums/$album/$title'),
            (u'singleton:true', u'tracks/$artist/$title'),
        ])
        self.lib.add(_common.item())
        self.lib.add_album([_common.item()])
        self.tree = vfs.libtree(self.lib)

    def test_singleton_item(self):
        self.assertEqual(self.tree.dirs['tracks'].dirs['the artist'].
                         files['the title'], 1)

    def test_album_item(self):
        self.assertEqual(self.tree.dirs['albums'].dirs['the album'].
                         files['the title'], 2)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
