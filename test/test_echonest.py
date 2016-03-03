# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Thomas Scholtes
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

import os.path
from mock import Mock, patch

from test._common import unittest, RSRC
from test.helper import TestHelper

from beets.library import Item


class EchonestCliTest(unittest.TestCase, TestHelper):
    def setUp(self):
        try:
            __import__('pyechonest')
        except ImportError:
            self.skipTest(u'pyechonest not available')

        self.setup_beets()
        self.load_plugins('echonest')
        # Prevent 'beet echonest' from writing files
        self.config['import']['write'] = False

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    @patch.object(Item, 'write')
    @patch('pyechonest.song.profile')
    @patch('pyechonest.track.track_from_id')
    def test_mbid_profile(self, echonest_track, echonest_profile, item_write):
        """Retrieve song info from MusicBrainz ID."""
        item = self.add_item(title='title', length=10, mb_trackid='1')
        profile = self.profile(item, energy=0.5, tempo=120, key=2, mode=0)
        echonest_profile.return_value = [profile]
        echonest_track.return_value = Mock(song_id='echonestid')

        self.assertNotIn('energy', item)
        self.assertNotEqual(item['bpm'], 120)
        self.assertNotIn('initialkey', item)

        self.run_command('echonest')
        item.load()
        self.assertEqual(item['energy'], 0.5)
        self.assertEqual(item['bpm'], 120)
        self.assertEqual(item['initial_key'], 'C#m')

    @patch('pyechonest.track.track_from_id')
    @patch('pyechonest.song.search')
    def test_song_search(self, echonest_search, echonest_track):
        item = self.add_item(title='title', length=10, mb_trackid='1')
        echonest_search.return_value = [self.profile(item, energy=0.1)]
        echonest_track.return_value = []

        self.run_command('echonest')
        item.load()
        self.assertEqual(item['energy'], 0.1)
        self.assertEqual(1, echonest_track.call_count)

    @patch('pyechonest.song.profile')
    @patch('pyechonest.song.search')
    @patch('pyechonest.track.track_from_filename')
    def test_analyze(self, echonest_track, echonest_search, echonest_profile):
        item = self.add_item(title='title', length=10,
                             path=os.path.join(RSRC, 'min.mp3'))
        echonest_search.return_value = []
        echonest_profile.return_value = [self.profile(item, energy=0.2)]
        echonest_track.return_value = self.track(item)

        self.run_command('echonest')
        item.load()
        self.assertEqual(item['energy'], 0.2)
        self.assertEqual(1, echonest_search.call_count)
        self.assertEqual(item.path,
                         echonest_track.call_args[1]['filename'])

    @patch('pyechonest.song.profile')
    @patch('pyechonest.song.search')
    @patch('pyechonest.track.track_from_filename')
    @patch('beetsplug.echonest.CONVERT_COMMAND', 'cp $source $dest')
    def test_analyze_convert(self, echonest_track, echonest_search,
                             echonest_profile):
        item = self.add_item(title='title', length=10, format='FLAC',
                             path=os.path.join(RSRC, 'min.flac'))
        echonest_search.return_value = []
        echonest_profile.return_value = [self.profile(item, energy=0.2)]
        echonest_track.return_value = self.track(item)

        self.run_command('echonest')
        item.load()
        self.assertEqual(item['energy'], 0.2)
        # Assert uploaded file was converted
        self.assertNotEqual(item.path,
                            echonest_track.call_args[1]['filename'])

    @patch('pyechonest.song.search')
    @patch('beetsplug.echonest.CONVERT_COMMAND', 'cp $source $dest')
    def test_analyze_convert2(self, echonest_search):
        self.add_item(format='FLAC', path=b'm\xc3\xacn.flac')
        self.run_command('echonest')

    @patch('pyechonest.song.profile')
    @patch('pyechonest.song.search')
    @patch('pyechonest.track.track_from_filename')
    @patch('beetsplug.echonest.CONVERT_COMMAND', 'false')
    def test_analyze_convert_fail(self, echonest_track, echonest_search,
                                  echonest_profile):
        item = self.add_item(title='title', length=10, format='FLAC',
                             path=os.path.join(RSRC, 'min.flac'))
        echonest_search.return_value = []
        echonest_profile.return_value = [self.profile(item, energy=0.2)]
        echonest_track.return_value = self.track(item)

        self.run_command('echonest')
        item.load()
        self.assertNotIn('energy', item)
        self.assertEqual(0, echonest_track.call_count)

    @patch('pyechonest.song.profile')
    @patch('pyechonest.song.search')
    @patch('pyechonest.track.track_from_filename')
    # Force truncation
    @patch('beetsplug.echonest.UPLOAD_MAX_SIZE', 0)
    @patch('beetsplug.echonest.TRUNCATE_COMMAND', 'cp $source $dest')
    def test_analyze_truncate(self, echonest_track, echonest_search,
                              echonest_profile):
        item = self.add_item(title='title', length=10, format='MP3',
                             path=os.path.join(RSRC, 'min.mp3'))
        echonest_search.return_value = []
        echonest_profile.return_value = [self.profile(item, energy=0.2)]
        echonest_track.return_value = self.track(item)

        self.run_command('echonest')
        item.load()
        self.assertEqual(item['energy'], 0.2)
        self.assertEqual(1, echonest_search.call_count)
        self.assertNotEqual(item.path,
                            echonest_track.call_args[1]['filename'])

    def test_custom_field_range_query(self):
        item = Item(liveness=2.2)
        item.add(self.lib)
        item = self.lib.items(u'liveness:2.2..3').get()
        self.assertEqual(item['liveness'], 2.2)

    def profile(self, item, **values):
        """Return a mock Echonest Profile object.

        The fields are set to match the item. Additional values are
        passed to the `audio_summary` dictionary of the profile.
        """
        audio_summary = {'duration': item.length}
        audio_summary.update(values)
        return Mock(
            artist_name=item.artist,
            title=item.title,
            id='echonestid',
            audio_summary=audio_summary
        )

    def track(self, item, **values):
        """Return a mock Echonest Track object.
        """
        values.update(
            duration=item.length,
            artist_name=item.artist,
            title=item.title,
            song_id='echonestid',
        )
        return Mock(**values)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
