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
import musicbrainzngs
from beets.autotag import AlbumInfo, TrackInfo, match
from beetsplug import ftintitle_mb
from test.helper import TestHelper

# used for fetching data with musicbrainzngs
RELEASE_INCLUDES = ['artists', 'media', 'recordings', 'release-groups',
                    'labels', 'artist-credits', 'aliases',
                    'recording-level-rels', 'work-rels',
                    'work-level-rels', 'artist-rels', 'isrcs']


class FtInTitleMBPluginTest(unittest.TestCase, TestHelper):

    def setUp(self):
        """Set up configuration"""
        self.setup_beets()
        self.load_plugins('ftintitle_mb')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def ftmb_config(self):
        self.config['ftintitle_mb']['feat_format'] = "(feat. {0})"
        self.config['ftintitle_mb']['collab_cases'] = [" & "]

    def ftmb_track(self, albumid, expected_title, expected_artist):
        """Test first track in an album"""
        match_test = match.match_by_id([AlbumInfo(mb_albumid=albumid,
                                        tracks=[TrackInfo()])])
        raw_test = \
            musicbrainzngs.get_release_by_id(albumid,
                                             RELEASE_INCLUDES)['release']

        ftintitle_mb.FtInTitleMBPlugin().update_metadata(
            match_test['tracks'][0],
            raw_test['medium-list'][0]['track-list'][0]['recording'])
        self.assertEqual(match_test['tracks'][0]['title'],
                         expected_title)
        self.assertEqual(match_test['tracks'][0]['artist'],
                         expected_artist)

    def test_ftintitle_mb(self):
        """Main test function"""

        # Apply testing config
        self.ftmb_config()

        # Test an artist with "&" in their name to show that it won't be
        # split like it would be using the normal ftintitle plugin.
        self.ftmb_track('3b675b27-c087-49e9-9e50-1875d88bf78c',
                        'Tompkins Square Park', 'Mumford & Sons')

        # TODO: Test an artist with & to show that it won't be split since we
        # have that in our collab_cases.
        #self.ftmb_track('3b675b27-c087-49e9-9e50-1875d88bf78c',
        #                'Tompkins Square Park', 'Mumford & Sons')

        # Finally, test an artist with a feature type not listed in
        # collab_cases. This should move that artist to the title using
        # our selected format.
        self.ftmb_track('71289422-f99c-47a9-ad2b-8f0969500dd0',
                        'Dig (feat. Sonny Rollins)', 'Miles Davis')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
