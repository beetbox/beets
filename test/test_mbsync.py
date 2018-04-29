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

import unittest
from mock import patch

from test.helper import TestHelper,\
    generate_album_info, \
    generate_track_info, \
    capture_log

from beets import config
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
            generate_track_info(u'singleton track id',
                                {'title': u'singleton info'})

        album_item = Item(
            album=u'old title',
            mb_albumid=u'album id',
            mb_trackid=u'track id',
            path=''
        )
        album = self.lib.add_album([album_item])

        item = Item(
            title=u'old title',
            mb_trackid=u'singleton track id',
            path='',
        )
        self.lib.add(item)

        self.run_command('mbsync')

        item.load()
        self.assertEqual(item.title, u'singleton info')

        album_item.load()
        self.assertEqual(album_item.title, u'track info')

        album.load()
        self.assertEqual(album.album, u'album info')

    def test_message_when_skipping(self):
        config['format_item'] = u'$artist - $album - $title'
        config['format_album'] = u'$albumartist - $album'

        # Test album with no mb_albumid.
        # The default format for an album include $albumartist so
        # set that here, too.
        album_invalid = Item(
            albumartist=u'album info',
            album=u'album info',
            path=''
        )
        self.lib.add_album([album_invalid])

        # default format
        with capture_log('beets.mbsync') as logs:
            self.run_command('mbsync')
        e = u'mbsync: Skipping album with no mb_albumid: ' + \
            u'album info - album info'
        self.assertEqual(e, logs[0])

        # custom format
        with capture_log('beets.mbsync') as logs:
            self.run_command('mbsync', '-f', "'$album'")
        e = u"mbsync: Skipping album with no mb_albumid: 'album info'"
        self.assertEqual(e, logs[0])

        # restore the config
        config['format_item'] = u'$artist - $album - $title'
        config['format_album'] = u'$albumartist - $album'

        # Test singleton with no mb_trackid.
        # The default singleton format includes $artist and $album
        # so we need to stub them here
        item_invalid = Item(
            artist=u'album info',
            album=u'album info',
            title=u'old title',
            path='',
        )
        self.lib.add(item_invalid)

        # default format
        with capture_log('beets.mbsync') as logs:
            self.run_command('mbsync')
        e = u'mbsync: Skipping singleton with no mb_trackid: ' + \
            u'album info - album info - old title'
        self.assertEqual(e, logs[0])

        # custom format
        with capture_log('beets.mbsync') as logs:
            self.run_command('mbsync', '-f', "'$title'")
        e = u"mbsync: Skipping singleton with no mb_trackid: 'old title'"
        self.assertEqual(e, logs[0])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
