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


import unittest
from unittest.mock import patch

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

    @patch('beets.autotag.mb.album_for_id')
    @patch('beets.autotag.mb.track_for_id')
    def test_update_library(self, track_for_id, album_for_id):
        album_for_id.return_value = \
            generate_album_info(
                'album id',
                [('track id', {'release_track_id': 'release track id'})]
            )
        track_for_id.return_value = \
            generate_track_info('singleton track id',
                                {'title': 'singleton info'})

        album_item = Item(
            album='old title',
            mb_albumid='81ae60d4-5b75-38df-903a-db2cfa51c2c6',
            mb_trackid='old track id',
            mb_releasetrackid='release track id',
            path=''
        )
        album = self.lib.add_album([album_item])

        item = Item(
            title='old title',
            mb_trackid='b8c2cf90-83f9-3b5f-8ccd-31fb866fcf37',
            path='',
        )
        self.lib.add(item)

        with capture_log() as logs:
            self.run_command('mbsync')

        self.assertIn('Sending event: albuminfo_received', logs)
        self.assertIn('Sending event: trackinfo_received', logs)

        item.load()
        self.assertEqual(item.title, 'singleton info')

        album_item.load()
        self.assertEqual(album_item.title, 'track info')
        self.assertEqual(album_item.mb_trackid, 'track id')

        album.load()
        self.assertEqual(album.album, 'album info')

    def test_message_when_skipping(self):
        config['format_item'] = '$artist - $album - $title'
        config['format_album'] = '$albumartist - $album'

        # Test album with no mb_albumid.
        # The default format for an album include $albumartist so
        # set that here, too.
        album_invalid = Item(
            albumartist='album info',
            album='album info',
            path=''
        )
        self.lib.add_album([album_invalid])

        # default format
        with capture_log('beets.mbsync') as logs:
            self.run_command('mbsync')
        e = 'mbsync: Skipping album with no mb_albumid: ' + \
            'album info - album info'
        self.assertEqual(e, logs[0])

        # custom format
        with capture_log('beets.mbsync') as logs:
            self.run_command('mbsync', '-f', "'$album'")
        e = "mbsync: Skipping album with no mb_albumid: 'album info'"
        self.assertEqual(e, logs[0])

        # restore the config
        config['format_item'] = '$artist - $album - $title'
        config['format_album'] = '$albumartist - $album'

        # Test singleton with no mb_trackid.
        # The default singleton format includes $artist and $album
        # so we need to stub them here
        item_invalid = Item(
            artist='album info',
            album='album info',
            title='old title',
            path='',
        )
        self.lib.add(item_invalid)

        # default format
        with capture_log('beets.mbsync') as logs:
            self.run_command('mbsync')
        e = 'mbsync: Skipping singleton with no mb_trackid: ' + \
            'album info - album info - old title'
        self.assertEqual(e, logs[0])

        # custom format
        with capture_log('beets.mbsync') as logs:
            self.run_command('mbsync', '-f', "'$title'")
        e = "mbsync: Skipping singleton with no mb_trackid: 'old title'"
        self.assertEqual(e, logs[0])

    def test_message_when_invalid(self):
        config['format_item'] = '$artist - $album - $title'
        config['format_album'] = '$albumartist - $album'

        # Test album with invalid mb_albumid.
        # The default format for an album include $albumartist so
        # set that here, too.
        album_invalid = Item(
            albumartist='album info',
            album='album info',
            mb_albumid='a1b2c3d4',
            path=''
        )
        self.lib.add_album([album_invalid])

        # default format
        with capture_log('beets.mbsync') as logs:
            self.run_command('mbsync')
        e = 'mbsync: Skipping album with invalid mb_albumid: ' + \
            'album info - album info'
        self.assertEqual(e, logs[0])

        # custom format
        with capture_log('beets.mbsync') as logs:
            self.run_command('mbsync', '-f', "'$album'")
        e = "mbsync: Skipping album with invalid mb_albumid: 'album info'"
        self.assertEqual(e, logs[0])

        # restore the config
        config['format_item'] = '$artist - $album - $title'
        config['format_album'] = '$albumartist - $album'

        # Test singleton with invalid mb_trackid.
        # The default singleton format includes $artist and $album
        # so we need to stub them here
        item_invalid = Item(
            artist='album info',
            album='album info',
            title='old title',
            mb_trackid='a1b2c3d4',
            path='',
        )
        self.lib.add(item_invalid)

        # default format
        with capture_log('beets.mbsync') as logs:
            self.run_command('mbsync')
        e = 'mbsync: Skipping singleton with invalid mb_trackid: ' + \
            'album info - album info - old title'
        self.assertEqual(e, logs[0])

        # custom format
        with capture_log('beets.mbsync') as logs:
            self.run_command('mbsync', '-f', "'$title'")
        e = "mbsync: Skipping singleton with invalid mb_trackid: 'old title'"
        self.assertEqual(e, logs[0])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
