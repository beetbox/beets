# This file is part of beets.
# Copyright 2014, Thomas Scholtes
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


from mock import Mock, patch

from _common import unittest
from helper import TestHelper

from beets.library import Item


class EchonestCliTest(unittest.TestCase, TestHelper):
    def setUp(self):
        try:
            __import__('pyechonest')
        except ImportError:
            self.skipTest('pyechonest not available')

        self.setup_beets()
        self.load_plugins('echonest')

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    @patch.object(Item, 'write')
    @patch('pyechonest.song.profile')
    @patch('pyechonest.track.track_from_id')
    def test_store_data(self, echonest_track, echonest_profile, item_write):
        profile = Mock(
            artist_name='artist',
            title='title',
            id='echonestid',
            audio_summary={
                'duration': 10,
                'energy': 0.5,
                'liveness': 0.5,
                'loudness': 0.5,
                'speechiness': 0.5,
                'danceability': 0.5,
                'tempo': 120,
                'key': 2,
                'mode': 0
            },
        )
        echonest_profile.return_value = [profile]
        echonest_track.return_value = Mock(song_id='echonestid')

        item = Item(
            mb_trackid='01234',
            artist='artist',
            title='title',
            length=10,
        )
        item.add(self.lib)
        self.assertNotIn('danceability', item)
        self.assertNotIn('initialkey', item)

        self.run_command('echonest')
        item.load()
        self.assertEqual(item['danceability'], '0.5')
        self.assertEqual(item['initial_key'], 'C#m')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
