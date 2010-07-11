# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

"""Tests for MusicBrainz API wrapper.
"""

import unittest
import sys
import os
import time
import re
import musicbrainz2.model
sys.path.append('..')
from beets.autotag import mb
from beets.library import Item

def nullfun(): pass
class MBQueryWaitTest(unittest.TestCase):
    def setup(self):
        # simulate startup
        mb.last_query_time = 0.0

    def test_do_not_wait_initially(self):
        time1 = time.time()
        mb._query_wrap(nullfun)
        time2 = time.time()
        self.assertTrue(time2 - time1 < 1.0)

    def test_second_rapid_query_waits(self):
        mb._query_wrap(nullfun)
        time1 = time.time()
        mb._query_wrap(nullfun)
        time2 = time.time()
        self.assertTrue(time2 - time1 > 1.0)

    def test_second_distant_query_does_not_wait(self):
        mb._query_wrap(nullfun)
        time.sleep(1.0)
        time1 = time.time()
        mb._query_wrap(nullfun)
        time2 = time.time()
        self.assertTrue(time2 - time1 < 1.0)

class MBReleaseDictTest(unittest.TestCase):
    def _make_release(self, date_str='2009'):
        release = musicbrainz2.model.Release()
        release.title = 'ALBUM TITLE'
        release.id = 'ALBUM ID'
        release.artist = musicbrainz2.model.Artist()
        release.artist.name = 'ARTIST NAME'
        release.artist.id = 'ARTIST ID'

        event = musicbrainz2.model.ReleaseEvent()
        if date_str is not None:
            event.date = date_str
        release.releaseEvents.append(event)

        return release

    def _make_track(self, title, tr_id, duration):
        track = musicbrainz2.model.Track()
        track.title = title
        track.id = tr_id
        if duration is not None:
            track.duration = duration
        return track
    
    def test_parse_release_with_year(self):
        release = self._make_release('1984')
        d = mb.release_dict(release)
        self.assertEqual(d['album'], 'ALBUM TITLE')
        self.assertEqual(d['album_id'], 'ALBUM ID')
        self.assertEqual(d['artist'], 'ARTIST NAME')
        self.assertEqual(d['artist_id'], 'ARTIST ID')
        self.assertEqual(d['year'], 1984)

    def test_parse_release_full_date(self):
        release = self._make_release('1987-03-31')
        d = mb.release_dict(release)
        self.assertEqual(d['year'], 1987)
        self.assertEqual(d['month'], 3)
        self.assertEqual(d['day'], 31)

    def test_parse_tracks(self):
        release = self._make_release()
        tracks = [self._make_track('TITLE ONE', 'ID ONE', 100.0 * 1000.0),
                  self._make_track('TITLE TWO', 'ID TWO', 200.0 * 1000.0)]
        d = mb.release_dict(release, tracks)
        t = d['tracks']
        self.assertEqual(len(t), 2)
        self.assertEqual(t[0]['title'], 'TITLE ONE')
        self.assertEqual(t[0]['id'], 'ID ONE')
        self.assertEqual(t[0]['length'], 100.0)
        self.assertEqual(t[1]['title'], 'TITLE TWO')
        self.assertEqual(t[1]['id'], 'ID TWO')
        self.assertEqual(t[1]['length'], 200.0)

    def test_parse_release_year_month_only(self):
        release = self._make_release('1987-03')
        d = mb.release_dict(release)
        self.assertEqual(d['year'], 1987)
        self.assertEqual(d['month'], 3)
    
    def test_no_durations(self):
        release = self._make_release()
        tracks = [self._make_track('TITLE', 'ID', None)]
        d = mb.release_dict(release, tracks)
        self.assertFalse('length' in d['tracks'][0])

    def test_no_release_date(self):
        release = self._make_release(None)
        d = mb.release_dict(release)
        self.assertFalse('year' in d)
        self.assertFalse('month' in d)
        self.assertFalse('day' in d)

class MBWhiteBoxTest(unittest.TestCase):
    def test_match_album_finds_el_producto(self):
        a = iter(mb.match_album('the avalanches', 'el producto')).next()
        self.assertEqual(a['album'], 'El Producto')
        self.assertEqual(a['artist'], 'The Avalanches')
        self.assertEqual(len(a['tracks']), 7)

    def test_match_album_tolerates_small_errors(self):
        a = iter(mb.match_album('mia', 'kala ')).next()
        self.assertEqual(a['artist'], 'M.I.A.')
        self.assertEqual(a['album'], 'Kala')

class ByIDTest(unittest.TestCase):
    def test_match_found(self):
        a = mb.album_for_id('73677f81-86e6-4087-9255-9ee81b8e3dd3')
        self.assertEqual(a['artist'], 'Paul Simon')
        self.assertEqual(a['album'], 'Graceland')
        self.assertTrue(len(a['tracks']) > 0)
    
    def test_no_match_returns_none(self):
        a = mb.album_for_id('bogus-id')
        self.assertEqual(a, None)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
