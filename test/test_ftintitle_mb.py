# This file is part of beets.
# Copyright 2022, dvcky.
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

"""Tests for the 'ftintitle_mb' plugin."""

import unittest
from beets.autotag import AlbumInfo, AlbumMatch, TrackInfo
from beetsplug import ftintitle_mb
from test.helper import TestHelper


class FtInTitleMBPluginTest(unittest.TestCase, TestHelper):
    """Testing class for ftintitle_mb"""

    def setUp(self):
        """Set up configuration"""
        self.setup_beets()
        self.load_plugins('ftintitle_mb')

    def tearDown(self):
        """Tear down configuration"""
        self.unload_plugins()
        self.teardown_beets()

    def ftmb_config(self):
        """Set ftintitle_mb configuration for testing"""
        self.config['ftintitle_mb']['feat_format'] = "(feat. {0})"
        self.config['ftintitle_mb']['collab_cases'] = [" & "]

    def ftmb_track(self, artistcredits, expected_title, expected_artist):
        """Test first track in an album"""
        match_test = AlbumMatch(0, AlbumInfo(tracks=[TrackInfo()]),
                                set(), set(), set())

        # this just creates test raw data, so that we don't need to
        # use musicbrainzngs
        raw_test = {
            'medium-list': [{
                'track-list': [{
                    'recording': {
                        'title': "ftmb!",
                        'artist-credit': artistcredits
                    }
                }]
            }]
        }

        # the meat and bones of the plugin, where it's actually used
        ftintitle_mb.FtInTitleMBPlugin().update_metadata(
            match_test.info['tracks'][0],
            raw_test['medium-list'][0]['track-list'][0]['recording'])

        # finally, verify that the result title and artist are correct
        self.assertEqual(match_test.info['tracks'][0]['title'],
                         expected_title)
        self.assertEqual(match_test.info['tracks'][0]['artist'],
                         expected_artist)

    def test_ftintitle_mb(self):
        """Main test function"""

        # Apply testing config
        self.ftmb_config()

        # Test an artist with "&" in their name to show that it won't be
        # split like it would be using the normal ftintitle plugin.
        test1_credits = [
            {'artist': {'name': 'Foo & Bar'}}
        ]
        self.ftmb_track(test1_credits, "ftmb!", "Foo & Bar")

        # Test an artists with & between them to show that it won't be split
        # since we have it in our collab_cases.
        test2_credits = [
            {'artist': {'name': 'Foo'}},
            ' & ',
            {'artist': {'name': 'Bar'}}
        ]
        self.ftmb_track(test2_credits, "ftmb!", "Foo & Bar")

        # Finally, test an artist with a feature type not listed in
        # collab_cases. This should move that artist to the title using
        # our selected format.
        test3_credits = [
            {'artist': {'name': 'Foo'}},
            ' featuring ',
            {'artist': {'name': 'Bar'}}
        ]
        self.ftmb_track(test3_credits, "ftmb! (feat. Bar)", "Foo")


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
