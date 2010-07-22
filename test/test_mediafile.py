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

"""Specific, edge-case tests for the MediaFile metadata layer.
"""

import unittest, sys, os, shutil, datetime
sys.path.append('..')
import beets.mediafile

class EdgeTest(unittest.TestCase):
    def test_emptylist(self):
        # Some files have an ID3 frame that has a list with no elements.
        # This is very hard to produce, so this is just the first 8192
        # bytes of a file found "in the wild".
        emptylist = beets.mediafile.MediaFile(
                                os.path.join('rsrc', 'emptylist.mp3'))
        genre = emptylist.genre
        self.assertEqual(genre, '')

    def test_release_time_with_space(self):
        # Ensures that release times delimited by spaces are ignored.
        # Amie Street produces such files.
        space_time = beets.mediafile.MediaFile(
                                os.path.join('rsrc', 'space_time.mp3'))
        self.assertEqual(space_time.year, 2009)
        self.assertEqual(space_time.month, 9)
        self.assertEqual(space_time.day, 4)

    def test_release_time_with_t(self):
        # Ensures that release times delimited by Ts are ignored.
        # The iTunes Store produces such files.
        t_time = beets.mediafile.MediaFile(
                                os.path.join('rsrc', 't_time.m4a'))
        self.assertEqual(t_time.year, 1987)
        self.assertEqual(t_time.month, 3)
        self.assertEqual(t_time.day, 31)

    def test_tempo_with_bpm(self):
        # Some files have a string like "128 BPM" in the tempo field
        # rather than just a number.
        f = beets.mediafile.MediaFile(os.path.join('rsrc', 'bpm.mp3'))
        self.assertEqual(f.bpm, 128)
    
    def test_discc_alternate_field(self):
        # Different taggers use different vorbis comments to reflect
        # the disc and disc count fields: ensure that the alternative
        # style works.
        f = beets.mediafile.MediaFile(os.path.join('rsrc', 'discc.ogg'))
        self.assertEqual(f.disc, 4)
        self.assertEqual(f.disctotal, 5)

class SafetyTest(unittest.TestCase):
    def _exccheck(self, fn, exc):
        fn = os.path.join('rsrc', fn)
        open(fn, 'a').close() # create an empty file (a la touch)
        self.assertRaises(exc, beets.mediafile.MediaFile, fn)
        os.unlink(fn) # delete the temporary file
    
    def test_corrupt_mp3_raises_unreadablefileerror(self):
        # Make sure we catch Mutagen reading errors appropriately.
        self._exccheck('corrupt.mp3', beets.mediafile.UnreadableFileError)
    
    def test_corrupt_mp4_raises_unreadablefileerror(self):
        self._exccheck('corrupt.m4a', beets.mediafile.UnreadableFileError)
    
    def test_corrupt_flac_raises_unreadablefileerror(self):
        self._exccheck('corrupt.flac', beets.mediafile.UnreadableFileError)
    
    def test_corrupt_ogg_raises_unreadablefileerror(self):
        self._exccheck('corrupt.ogg', beets.mediafile.UnreadableFileError)
    
    def test_corrupt_monkeys_raises_unreadablefileerror(self):
        self._exccheck('corrupt.ape', beets.mediafile.UnreadableFileError)
    
    def test_invalid_extension_raises_filetypeerror(self):
        self._exccheck('something.unknown', beets.mediafile.FileTypeError)

class SideEffectsTest(unittest.TestCase):
    def setUp(self):
        self.empty = os.path.join('rsrc', 'empty.mp3')

    def test_opening_tagless_file_leaves_untouched(self):
        old_mtime = os.stat(self.empty).st_mtime
        beets.mediafile.MediaFile(self.empty)
        new_mtime = os.stat(self.empty).st_mtime
        self.assertEqual(old_mtime, new_mtime)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
