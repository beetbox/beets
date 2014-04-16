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

from mock import patch

from _common import unittest
from helper import TestHelper,\
    generate_album_info, \
    generate_track_info

from beets.library import Item


class MbsyncCliTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()
        self.load_plugins('mbsync')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    @patch('beets.autotag.hooks.album_for_mbid')
    @patch('beets.autotag.hooks.track_for_mbid')
    def test_update_library(self, track_for_mbid, album_for_mbid):
        album_for_mbid.return_value = \
            generate_album_info('album id', ['track id'])
        track_for_mbid.return_value = \
            generate_track_info('singleton track id',
                                {'title': 'singleton info'})

        album_item = Item(
            title='old title',
            mb_albumid='album id',
            mb_trackid='track id',
            path=''
        )
        album = self.lib.add_album([album_item])

        item = Item(
            title='old title',
            mb_trackid='singleton track id',
            path='',
        )
        self.lib.add(item)

        self.run_command('mbsync')

        item.load()
        self.assertEqual(item.title, 'singleton info')

        album_item.load()
        self.assertEqual(album_item.title, 'track info')

        album.load()
        self.assertEqual(album.album, 'album info')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
