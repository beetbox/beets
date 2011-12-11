# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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

import unittest
import os
import shutil
import datetime

import _common
import beets.mediafile


def MakeReadingTest(path, correct_dict, field):
    class ReadingTest(unittest.TestCase):
        def setUp(self):
            self.f = beets.mediafile.MediaFile(path)
        def runTest(self):
            got = getattr(self.f, field)
            correct = correct_dict[field]
            message = field + ' incorrect (expected ' + repr(correct) + \
                      ', got ' + repr(got) + ') when testing ' + \
                      os.path.basename(path)
            if isinstance(correct, float):
                self.assertAlmostEqual(got, correct, msg=message)
            else:
                self.assertEqual(got, correct, message)
    return ReadingTest

def MakeReadOnlyTest(path, field, value):
    class ReadOnlyTest(unittest.TestCase):
        def setUp(self):
            self.f = beets.mediafile.MediaFile(path)
        def runTest(self):
            got = getattr(self.f, field)
            fail_msg = field + ' incorrect (expected ' + \
                       repr(value) + ', got ' + repr(got) + \
                       ') on ' + os.path.basename(path)
            if field == 'length':
                self.assertTrue(value-0.1 < got < value+0.1, fail_msg)
            else:
                self.assertEqual(got, value, fail_msg)
    return ReadOnlyTest

def MakeWritingTest(path, correct_dict, field, testsuffix='_test'):
    
    class WritingTest(unittest.TestCase):
        def setUp(self):
            # make a copy of the file we'll work on
            root, ext = os.path.splitext(path)
            self.tpath = root + testsuffix + ext
            shutil.copy(path, self.tpath)
            
            # generate the new value we'll try storing
            if field == 'art':
                self.value = 'xxx'
            elif type(correct_dict[field]) is unicode:
                self.value = u'TestValue: ' + field
            elif type(correct_dict[field]) is int:
                self.value = correct_dict[field] + 42
            elif type(correct_dict[field]) is bool:
                self.value = not correct_dict[field]
            elif type(correct_dict[field]) is datetime.date:
                self.value = correct_dict[field] + datetime.timedelta(42)
            elif type(correct_dict[field]) is str:
                self.value = 'TestValue-' + str(field)
            elif type(correct_dict[field]) is float:
                self.value = 9.87
            else:
                raise ValueError('unknown field type ' + \
                        str(type(correct_dict[field])))
        
        def runTest(self):    
            # write new tag
            a = beets.mediafile.MediaFile(self.tpath)
            setattr(a, field, self.value)
            a.save()
            
            # verify ALL tags are correct with modification
            b = beets.mediafile.MediaFile(self.tpath)
            for readfield in correct_dict.keys():
                got = getattr(b, readfield)
                
                # Make sure the modified field was changed correctly...
                if readfield == field:
                    message = field + ' modified incorrectly (changed to ' + \
                              repr(self.value) + ' but read ' + repr(got) + \
                              ') when testing ' + os.path.basename(path)
                    if isinstance(self.value, float):
                        self.assertAlmostEqual(got, self.value, msg=message)
                    else:
                        self.assertEqual(got, self.value, message)
                
                # ... and that no other field was changed.
                else:
                    # MPEG-4: ReplayGain not implented.
                    if 'm4a' in path and readfield.startswith('rg_'):
                        continue

                    # The value should be what it was originally most of the
                    # time.
                    correct = correct_dict[readfield]
                    
                    # The date field, however, is modified when its components
                    # change.
                    if readfield=='date' and field in ('year', 'month', 'day'):
                        try:
                            correct = datetime.date(
                               self.value if field=='year' else correct.year,
                               self.value if field=='month' else correct.month,
                               self.value if field=='day' else correct.day
                            )
                        except ValueError:
                            correct = datetime.date.min
                    # And vice-versa.
                    if field=='date' and readfield in ('year', 'month', 'day'):
                        correct = getattr(self.value, readfield)
                    
                    message = readfield + ' changed when it should not have' \
                              ' (expected ' + repr(correct) + ', got ' + \
                              repr(got) + ') when modifying ' + field + \
                              ' in ' + os.path.basename(path)
                    if isinstance(correct, float):
                        self.assertAlmostEqual(got, correct, msg=message)
                    else:
                        self.assertEqual(got, correct, message)
                
        def tearDown(self):
            if os.path.exists(self.tpath):
                os.remove(self.tpath)
    
    return WritingTest

correct_dicts = {

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

        'rg_track_peak': 0.0,
        'rg_track_gain': 0.0,
        'rg_album_peak': 0.0,
        'rg_album_gain': 0.0,
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
    },
    
    # Full release date.
    'date': {
        'year':       1987,
        'month':      3,
        'day':        31,
        'date':       datetime.date(1987, 3, 31)
    },

}

read_only_correct_dicts = {
    'full.mp3': {
        'length': 1.0,
        'bitrate': 80000,
        'format': 'MP3',
    },

    'full.flac': {
        'length': 1.0,
        'bitrate': 175120,
        'format': 'FLAC',
    },

    'full.m4a': {
        'length': 1.0,
        'bitrate': 64000,
        'format': 'AAC',
    },
    
    'full.ogg': {
        'length': 1.0,
        'bitrate': 48000,
        'format': 'OGG',
    },
    
    'full.ape': {
        'length': 1.0,
        'bitrate': 112040,
        'format': 'APE',
    },

    'full.wv': {
        'length': 1.0,
        'bitrate': 108744,
        'format': 'WavPack',
    },

    'full.mpc': {
        'length': 1.0,
        'bitrate': 23,
        'format': 'Musepack',
    },
}

def suite_for_file(path, correct_dict, writing=True):
    s = unittest.TestSuite()
    for field in correct_dict:
        if 'm4a' in path and field.startswith('rg_'):
            # MPEG-4 files: ReplayGain values not implemented.
            continue
        s.addTest(MakeReadingTest(path, correct_dict, field)())
        if writing and \
           not (   field == 'month' and correct_dict['year']  == 0
                or field == 'day'   and correct_dict['month'] == 0):
             # ensure that we don't test fields that can't be modified
             s.addTest(MakeWritingTest(path, correct_dict, field)())
    return s

test_files = {
    'm4a': ['full', 'partial', 'min'],
    'mp3': ['full', 'partial', 'min'],
    'flac': ['full', 'partial', 'min'],
    'ogg': ['full'],
    'ape': ['full'],
    'wv': ['full'],
    'mpc': ['full'],
}

def suite():
    s = unittest.TestSuite()
    
    # General tests.
    for kind, tagsets in test_files.items():
        for tagset in tagsets:
            path = os.path.join(_common.RSRC, tagset + '.' + kind)
            correct_dict = correct_dicts[tagset]
            for test in suite_for_file(path, correct_dict):
                s.addTest(test)
    
    # Special test for missing ID3 tag.
    for test in suite_for_file(os.path.join(_common.RSRC, 'empty.mp3'),
                               correct_dicts['empty'],
                               writing=False):
        s.addTest(test)
    
    # Special test for advanced release date.
    for test in suite_for_file(os.path.join(_common.RSRC, 'date.mp3'),
                               correct_dicts['date']):
        s.addTest(test)

    # Read-only attribute tests.
    for fname, correct_dict in read_only_correct_dicts.iteritems():
        path = os.path.join(_common.RSRC, fname)
        for field, value in correct_dict.iteritems():
            s.addTest(MakeReadOnlyTest(path, field, value)())
    
    return s

def test_nose_suite():
    for test in suite():
        yield test

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
