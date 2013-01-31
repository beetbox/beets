# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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

"""Automatically-generated blanket testing for the MediaFile metadata
layer.
"""
import os
import shutil
import datetime

import _common
from _common import unittest
import beets.mediafile

CORRECT_DICTS = {

    # All of the fields iTunes supports that we do also.
    'full': {
        'title':      u'full',
        'artist':     u'the artist',
        'album':      u'the album',
        'genre':      u'the genre',
        'composer':   u'the composer',
        'grouping':   u'the grouping',
        'year':       2001,
        'month':      0,
        'day':        0,
        'date':       datetime.date(2001, 1, 1),
        'track':      2,
        'tracktotal': 3,
        'disc':       4,
        'disctotal':  5,
        'lyrics':     u'the lyrics',
        'comments':   u'the comments',
        'bpm':        6,
        'comp':       True,
        'mb_trackid': '8b882575-08a5-4452-a7a7-cbb8a1531f9e',
        'mb_albumid': '9e873859-8aa4-4790-b985-5a953e8ef628',
        'mb_artistid':'7cf0ea9d-86b9-4dad-ba9e-2355a64899ea',
        'art':        None,
        'label':      u'the label',
    },

    # Additional coverage for common cases when "total" fields are unset.
    # Created with iTunes. (Also tests unset MusicBrainz fields.)
    'partial': {
        'track':      2,
        'tracktotal': 0,
        'disc':       4,
        'disctotal':  0,
        'mb_trackid': '',
        'mb_albumid': '',
        'mb_artistid':'',
    },
    'min': {
        'track':      0,
        'tracktotal': 0,
        'disc':       0,
        'disctotal':  0
    },

    # ID3 tag deleted with `mp3info -d`. Tests default values.
    'empty': {
        'title':      u'',
        'artist':     u'',
        'album':      u'',
        'genre':      u'',
        'composer':   u'',
        'grouping':   u'',
        'year':       0,
        'month':      0,
        'day':        0,
        'date':       datetime.date.min,
        'track':      0,
        'tracktotal': 0,
        'disc':       0,
        'disctotal':  0,
        'lyrics':     u'',
        'comments':   u'',
        'bpm':        0,
        'comp':       False,
        'mb_trackid': u'',
        'mb_albumid': u'',
        'mb_artistid':u'',
        'art':        None,
        'label':      u'',

        # Additional, non-iTunes fields.
        'rg_track_peak':        0.0,
        'rg_track_gain':        0.0,
        'rg_album_peak':        0.0,
        'rg_album_gain':        0.0,
        'albumartist':          u'',
        'mb_albumartistid':     u'',
        'artist_sort':          u'',
        'albumartist_sort':     u'',
        'acoustid_fingerprint': u'',
        'acoustid_id':          u'',
        'mb_releasegroupid':    u'',
        'asin':                 u'',
        'catalognum':           u'',
        'disctitle':            u'',
        'encoder':              u'',
        'script':               u'',
        'language':             u'',
        'country':              u'',
        'albumstatus':          u'',
        'media':                u'',
        'albumdisambig':        u'',
        'artist_credit':        u'',
        'albumartist_credit':   u'',
    },

    # Full release date.
    'date': {
        'year':       1987,
        'month':      3,
        'day':        31,
        'date':       datetime.date(1987, 3, 31)
    },

}

READ_ONLY_CORRECT_DICTS = {
    'full.mp3': {
        'length': 1.0,
        'bitrate': 80000,
        'format': 'MP3',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    },

    'full.flac': {
        'length': 1.0,
        'bitrate': 175120,
        'format': 'FLAC',
        'samplerate': 44100,
        'bitdepth': 16,
        'channels': 1,
    },

    'full.m4a': {
        'length': 1.0,
        'bitrate': 64000,
        'format': 'AAC',
        'samplerate': 44100,
        'bitdepth': 16,
        'channels': 2,
    },

    'full.ogg': {
        'length': 1.0,
        'bitrate': 48000,
        'format': 'OGG',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    },

    'full.ape': {
        'length': 1.0,
        'bitrate': 112040,
        'format': 'APE',
        'samplerate': 44100,
        'bitdepth': 16,
        'channels': 1,
    },

    'full.wv': {
        'length': 1.0,
        'bitrate': 108744,
        'format': 'WavPack',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    },

    'full.mpc': {
        'length': 1.0,
        'bitrate': 23458,
        'format': 'Musepack',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 2,
    },

    'full.wma': {
        'length': 1.0,
        'bitrate': 128000,
        'format': 'Windows Media',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    },
}

TEST_FILES = {
    'm4a': ['full', 'partial', 'min'],
    'mp3': ['full', 'partial', 'min'],
    'flac': ['full', 'partial', 'min'],
    'ogg': ['full'],
    'ape': ['full'],
    'wv': ['full'],
    'mpc': ['full'],
    'wma': ['full'],
}

class AllFilesMixin(object):
    """This is a dumb bit of copypasta but unittest has no supported
    method of generating tests at runtime.
    """
    def test_m4a_full(self):
        self._run('full', 'm4a')

    def test_m4a_partial(self):
        self._run('partial', 'm4a')

    def test_m4a_min(self):
        self._run('min', 'm4a')

    def test_mp3_full(self):
        self._run('full', 'mp3')

    def test_mp3_partial(self):
        self._run('partial', 'mp3')

    def test_mp3_min(self):
        self._run('min', 'mp3')

    def test_flac_full(self):
        self._run('full', 'flac')

    def test_flac_partial(self):
        self._run('partial', 'flac')

    def test_flac_min(self):
        self._run('min', 'flac')

    def test_ogg(self):
        self._run('full', 'ogg')

    def test_ape(self):
        self._run('full', 'ape')

    def test_wv(self):
        self._run('full', 'wv')

    def test_mpc(self):
        self._run('full', 'mpc')

    def test_wma(self):
        self._run('full', 'wma')

    # Special test for advanced release date.
    def test_date_mp3(self):
        self._run('date', 'mp3')

class ReadingTest(unittest.TestCase, AllFilesMixin):
    def _read_field(self, mf, correct_dict, field):
        got = getattr(mf, field)
        correct = correct_dict[field]
        message = field + ' incorrect (expected ' + repr(correct) + \
                    ', got ' + repr(got) + ')'
        if isinstance(correct, float):
            self.assertAlmostEqual(got, correct, msg=message)
        else:
            self.assertEqual(got, correct, message)
    
    def _run(self, tagset, kind):
        correct_dict = CORRECT_DICTS[tagset]
        path = os.path.join(_common.RSRC, tagset + '.' + kind)
        f = beets.mediafile.MediaFile(path)
        for field in correct_dict:
            if 'm4a' in path and field.startswith('rg_'):
                # MPEG-4 files: ReplayGain values not implemented.
                continue
            self._read_field(f, correct_dict, field)

    # Special test for missing ID3 tag.
    def test_empy_mp3(self):
        self._run('empty', 'mp3')

class WritingTest(unittest.TestCase, AllFilesMixin):
    def _write_field(self, tpath, field, value, correct_dict):
        # Write new tag.
        a = beets.mediafile.MediaFile(tpath)
        setattr(a, field, value)
        a.save()

        # Verify ALL tags are correct with modification.
        b = beets.mediafile.MediaFile(tpath)
        for readfield in correct_dict.keys():
            got = getattr(b, readfield)

            # Make sure the modified field was changed correctly...
            if readfield == field:
                message = field + ' modified incorrectly (changed to ' + \
                            repr(value) + ' but read ' + repr(got) + ')'
                if isinstance(value, float):
                    self.assertAlmostEqual(got, value, msg=message)
                else:
                    self.assertEqual(got, value, message)

            # ... and that no other field was changed.
            else:
                # MPEG-4: ReplayGain not implented.
                if 'm4a' in tpath and readfield.startswith('rg_'):
                    continue

                # The value should be what it was originally most of the
                # time.
                correct = correct_dict[readfield]

                # The date field, however, is modified when its components
                # change.
                if readfield=='date' and field in ('year', 'month', 'day'):
                    try:
                        correct = datetime.date(
                            value if field=='year' else correct.year,
                            value if field=='month' else correct.month,
                            value if field=='day' else correct.day
                        )
                    except ValueError:
                        correct = datetime.date.min
                # And vice-versa.
                if field=='date' and readfield in ('year', 'month', 'day'):
                    correct = getattr(value, readfield)

                message = readfield + ' changed when it should not have' \
                            ' (expected ' + repr(correct) + ', got ' + \
                            repr(got) + ') when modifying ' + field
                if isinstance(correct, float):
                    self.assertAlmostEqual(got, correct, msg=message)
                else:
                    self.assertEqual(got, correct, message)

    def _run(self, tagset, kind):
        correct_dict = CORRECT_DICTS[tagset]
        path = os.path.join(_common.RSRC, tagset + '.' + kind)

        for field in correct_dict:
            if field == 'month' and correct_dict['year']  == 0 or \
            field == 'day'   and correct_dict['month'] == 0:
                continue

            # Generate the new value we'll try storing.
            if field == 'art':
                value = 'xxx'
            elif type(correct_dict[field]) is unicode:
                value = u'TestValue: ' + field
            elif type(correct_dict[field]) is int:
                value = correct_dict[field] + 42
            elif type(correct_dict[field]) is bool:
                value = not correct_dict[field]
            elif type(correct_dict[field]) is datetime.date:
                value = correct_dict[field] + datetime.timedelta(42)
            elif type(correct_dict[field]) is str:
                value = 'TestValue-' + str(field)
            elif type(correct_dict[field]) is float:
                value = 9.87
            else:
                raise ValueError('unknown field type ' + \
                        str(type(correct_dict[field])))
            
            # Make a copy of the file we'll work on.
            root, ext = os.path.splitext(path)
            tpath = root + '_test' + ext
            shutil.copy(path, tpath)

            try:
                self._write_field(tpath, field, value, correct_dict)
            finally:
                os.remove(tpath)

class ReadOnlyTest(unittest.TestCase):
    def _read_field(self, mf, field, value):
        got = getattr(mf, field)
        fail_msg = field + ' incorrect (expected ' + \
                    repr(value) + ', got ' + repr(got) + ')'
        if field == 'length':
            self.assertTrue(value-0.1 < got < value+0.1, fail_msg)
        else:
            self.assertEqual(got, value, fail_msg)

    def _run(self, filename):
        path = os.path.join(_common.RSRC, filename)
        f = beets.mediafile.MediaFile(path)
        correct_dict = READ_ONLY_CORRECT_DICTS[filename]
        for field, value in correct_dict.items():
            self._read_field(f, field, value)

    def test_mp3(self):
        self._run('full.mp3')

    def test_m4a(self):
        self._run('full.m4a')

    def test_flac(self):
        self._run('full.flac')

    def test_ogg(self):
        self._run('full.ogg')

    def test_ape(self):
        self._run('full.ape')

    def test_wv(self):
        self._run('full.wv')

    def test_mpc(self):
        self._run('full.mpc')

    def test_wma(self):
        self._run('full.wma')

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
