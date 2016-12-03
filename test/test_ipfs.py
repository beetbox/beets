# -*- coding: utf-8 -*-
# This file is part of beets.
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

from mock import patch, Mock

from beets import library
from beets.util import bytestring_path, _fsencoding
from beetsplug.ipfs import IPFSPlugin

import unittest
import os

from test import _common
from test.helper import TestHelper


@patch('beets.util.command_output', Mock())
class IPFSPluginTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()
        self.load_plugins('ipfs')
        self.lib = library.Library(":memory:")

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_stored_hashes(self):
        test_album = self.mk_test_album()
        ipfs = IPFSPlugin()
        added_albums = ipfs.ipfs_added_albums(self.lib, self.lib.path)
        added_album = added_albums.get_album(1)
        self.assertEqual(added_album.ipfs, test_album.ipfs)
        found = False
        want_item = test_album.items()[2]
        for check_item in added_album.items():
            try:
                if check_item.ipfs:
                    ipfs_item = os.path.basename(want_item.path).decode(
                        _fsencoding(),
                    )
                    want_path = '/ipfs/{0}/{1}'.format(test_album.ipfs,
                                                       ipfs_item)
                    want_path = bytestring_path(want_path)
                    self.assertEqual(check_item.path, want_path)
                    self.assertEqual(check_item.ipfs, want_item.ipfs)
                    self.assertEqual(check_item.title, want_item.title)
                    found = True
            except AttributeError:
                pass
        self.assertTrue(found)

    def mk_test_album(self):
        items = [_common.item() for _ in range(3)]
        items[0].title = 'foo bar'
        items[0].artist = 'one'
        items[0].album = 'baz'
        items[0].year = 2001
        items[0].comp = True
        items[1].title = 'baz qux'
        items[1].artist = 'two'
        items[1].album = 'baz'
        items[1].year = 2002
        items[1].comp = True
        items[2].title = 'beets 4 eva'
        items[2].artist = 'three'
        items[2].album = 'foo'
        items[2].year = 2003
        items[2].comp = False
        items[2].ipfs = 'QmfM9ic5LJj7V6ecozFx1MkSoaaiq3PXfhJoFvyqzpLXSk'

        for item in items:
            self.lib.add(item)

        album = self.lib.add_album(items)
        album.ipfs = "QmfM9ic5LJj7V6ecozFx1MkSoaaiq3PXfhJoFvyqzpLXSf"
        album.store()

        return album


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
