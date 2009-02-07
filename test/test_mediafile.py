#!/usr/bin/env python

"""
Test the MediaFile metadata layer.
"""

import unittest, sys, os, shutil, datetime
sys.path.append('..')
import beets.mediafile


def MakeReadingTest(path, correct_dict, field):
    class ReadingTest(unittest.TestCase):
        def setUp(self):
            self.f = beets.mediafile.MediaFile(path)
        def runTest(self):
            got = getattr(self.f, field)
            correct = correct_dict[field]
            self.assertEqual(got, correct,
                field + ' incorrect (expected ' + repr(correct) + ', got ' + \
                repr(got) + ') when testing ' + os.path.basename(path))
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
            if type(correct_dict[field]) is unicode:
                self.value = u'TestValue: ' + field
            elif type(correct_dict[field]) is int:
                self.value = correct_dict[field] + 42
            elif type(correct_dict[field]) is bool:
                self.value = not correct_dict[field]
            elif type(correct_dict[field]) is datetime.date:
                self.value = correct_dict[field] + datetime.timedelta(42)
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
                    self.assertEqual(got, self.value,
                        field + ' modified incorrectly (changed to ' + \
                        repr(self.value) + ' but read ' + repr(got) + \
                        ') when testing ' + os.path.basename(path))
                
                # ... and that no other field was changed.
                else:
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
                    
                    self.assertEqual(got, correct,
                        readfield + ' changed when it should not have (expected'
                        ' ' + repr(correct) + ', got ' + repr(got) + ') when '
                        'modifying ' + field + ' in ' + os.path.basename(path))
                
        def tearDown(self):
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
        'comp':       True
    },

    # Additional coverage for common cases when "total" fields are unset.
    # Created with iTunes.
    'partial': {
        'track':      2,
        'tracktotal': 0,
        'disc':       4,
        'disctotal':  0
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
        'comp':       False
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
    },

    'full.flac': {
        'length': 1.0,
        'bitrate': 705600,
    },

    'full.m4a': {
        'length': 1.0,
        'bitrate': 64000,
    },

}

def suite_for_file(path, correct_dict, writing=True):
    s = unittest.TestSuite()
    for field in correct_dict:
        s.addTest(MakeReadingTest(path, correct_dict, field)())
        if writing and \
           not (   field == 'month' and correct_dict['year']  == 0
                or field == 'day'   and correct_dict['month'] == 0):
             # ensure that we don't test fields that can't be modified
             s.addTest(MakeWritingTest(path, correct_dict, field)())
    return s

def suite():
    s = unittest.TestSuite()
    
    # General tests.
    for kind in ('m4a', 'mp3', 'flac'):
        for tagset in ('full', 'partial', 'min'):
            path = os.path.join('rsrc', tagset + '.' + kind)
            correct_dict = correct_dicts[tagset]
            s.addTest(suite_for_file(path, correct_dict))
    
    # Special test for missing ID3 tag.
    s.addTest(suite_for_file(os.path.join('rsrc', 'empty.mp3'),
                             correct_dicts['empty'],
                             writing=False))
    
    # Special test for advanced release date.
    s.addTest(suite_for_file(os.path.join('rsrc', 'date.mp3'),
                             correct_dicts['date']))

    # Test for dates that include times (like iTunes purchases).
    s.addTest(suite_for_file(os.path.join('rsrc', 'time.m4a'),
                             correct_dicts['date']))

    # Read-only attribute tests.
    for fname, correct_dict in read_only_correct_dicts.iteritems():
        path = os.path.join('rsrc', fname)
        for field, value in correct_dict.iteritems():
            s.addTest(MakeReadOnlyTest(path, field, value)())
    
    return s

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
