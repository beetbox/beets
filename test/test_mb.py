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
import time
import musicbrainz2.model
import musicbrainz2.webservice as mbws
import httplib

import _common
from beets.autotag import mb

def nullfun(): pass
class MBQueryWaitTest(unittest.TestCase):
    def setUp(self):
        # simulate startup
        mb.last_query_time = 0.0
        self.cop = _common.Timecop()
        self.cop.install()

    def tearDown(self):
        self.cop.restore()

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
        self.assertTrue(time2 - time1 >= 1.0)

    def test_second_distant_query_does_not_wait(self):
        mb._query_wrap(nullfun)
        time.sleep(1.0)
        time1 = time.time()
        mb._query_wrap(nullfun)
        time2 = time.time()
        self.assertTrue(time2 - time1 < 1.0)

def raise_once_func(exc):
    count = [0] # use a list to get a reference (avoid need for nonlocal)
    def fun():
        count[0] += 1
        if count[0] == 1:
            raise exc
        else:
            return 1
    return fun
def raise_func(exc):
    def fun():
        raise exc
    return fun
class MBQueryErrorTest(unittest.TestCase):
    def setUp(self):
        mb.last_query_time = 0.0
        self.cop = _common.Timecop()
        self.cop.install()

    def tearDown(self):
        self.cop.restore()

    def test_503_error_retries(self):
        exc = mbws.WebServiceError(reason=Exception('Error 503'))
        mb._query_wrap(raise_once_func(exc))

    def test_504_error_retries(self):
        exc = mbws.WebServiceError(reason=Exception('Error 504'))
        mb._query_wrap(raise_once_func(exc))

    def test_status_line_error_retries(self):
        exc = httplib.BadStatusLine('dummy')
        mb._query_wrap(raise_once_func(exc))

    def test_999_error_passes_through(self):
        exc = mbws.WebServiceError(reason=Exception('Error 999'))
        with self.assertRaises(mbws.WebServiceError):
            mb._query_wrap(raise_once_func(exc))

    def test_repeated_error_raises_busy(self):
        exc = mbws.WebServiceError(reason=Exception('Error 503'))
        with self.assertRaises(mb.ServerBusyError):
            mb._query_wrap(raise_func(exc))

class MBReleaseDictTest(unittest.TestCase):
    def _make_release(self, date_str='2009'):
        release = musicbrainz2.model.Release()
        release.title = 'ALBUM TITLE'
        release.id = 'domain/ALBUM ID'
        release.addType(musicbrainz2.model.Release.TYPE_ALBUM)
        release.addType(musicbrainz2.model.Release.TYPE_OFFICIAL)
        release.artist = musicbrainz2.model.Artist()
        release.artist.name = 'ARTIST NAME'
        release.artist.id = 'domain/ARTIST ID'

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

    def test_parse_release_type(self):
        release = self._make_release('1984')
        d = mb.release_dict(release)
        self.assertEqual(d['albumtype'], 'album')

    def test_parse_release_full_date(self):
        release = self._make_release('1987-03-31')
        d = mb.release_dict(release)
        self.assertEqual(d['year'], 1987)
        self.assertEqual(d['month'], 3)
        self.assertEqual(d['day'], 31)

    def test_parse_tracks(self):
        release = self._make_release()
        tracks = [self._make_track('TITLE ONE', 'dom/ID ONE', 100.0 * 1000.0),
                  self._make_track('TITLE TWO', 'dom/ID TWO', 200.0 * 1000.0)]
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
        tracks = [self._make_track('TITLE', 'dom/ID', None)]
        d = mb.release_dict(release, tracks)
        self.assertFalse('length' in d['tracks'][0])

    def test_no_release_date(self):
        release = self._make_release(None)
        d = mb.release_dict(release)
        self.assertFalse('year' in d)
        self.assertFalse('month' in d)
        self.assertFalse('day' in d)

    def test_various_artists_defaults_false(self):
        release = self._make_release(None)
        d = mb.release_dict(release)
        self.assertFalse(d['va'])

    def test_detect_various_artists(self):
        release = self._make_release(None)
        release.artist.id = musicbrainz2.model.VARIOUS_ARTISTS_ID
        d = mb.release_dict(release)
        self.assertTrue(d['va'])

class QuerySanitationTest(unittest.TestCase):
    def test_special_char_escaped(self):
        res = mb._lucene_escape('!')
        self.assertEqual(res, '\\!')

    def test_null_character_removed(self):
        res = mb._lucene_escape('\0')
        self.assertEqual(res, '')

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
