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

import unittest
import os
import shutil

import _common
import beets.mediafile

class EdgeTest(unittest.TestCase):
    def test_emptylist(self):
        # Some files have an ID3 frame that has a list with no elements.
        # This is very hard to produce, so this is just the first 8192
        # bytes of a file found "in the wild".
        emptylist = beets.mediafile.MediaFile(
                                os.path.join(_common.RSRC, 'emptylist.mp3'))
        genre = emptylist.genre
        self.assertEqual(genre, '')

    def test_release_time_with_space(self):
        # Ensures that release times delimited by spaces are ignored.
        # Amie Street produces such files.
        space_time = beets.mediafile.MediaFile(
                                os.path.join(_common.RSRC, 'space_time.mp3'))
        self.assertEqual(space_time.year, 2009)
        self.assertEqual(space_time.month, 9)
        self.assertEqual(space_time.day, 4)

    def test_release_time_with_t(self):
        # Ensures that release times delimited by Ts are ignored.
        # The iTunes Store produces such files.
        t_time = beets.mediafile.MediaFile(
                                os.path.join(_common.RSRC, 't_time.m4a'))
        self.assertEqual(t_time.year, 1987)
        self.assertEqual(t_time.month, 3)
        self.assertEqual(t_time.day, 31)

    def test_tempo_with_bpm(self):
        # Some files have a string like "128 BPM" in the tempo field
        # rather than just a number.
        f = beets.mediafile.MediaFile(os.path.join(_common.RSRC, 'bpm.mp3'))
        self.assertEqual(f.bpm, 128)
    
    def test_discc_alternate_field(self):
        # Different taggers use different vorbis comments to reflect
        # the disc and disc count fields: ensure that the alternative
        # style works.
        f = beets.mediafile.MediaFile(os.path.join(_common.RSRC, 'discc.ogg'))
        self.assertEqual(f.disc, 4)
        self.assertEqual(f.disctotal, 5)

    def test_old_ape_version_bitrate(self):
        f = beets.mediafile.MediaFile(os.path.join(_common.RSRC, 'oldape.ape'))
        self.assertEqual(f.bitrate, 0)

_sc = beets.mediafile._safe_cast
class InvalidValueToleranceTest(unittest.TestCase):
    def test_packed_integer_with_extra_chars(self):
        pack = beets.mediafile.Packed("06a", beets.mediafile.packing.SLASHED)
        self.assertEqual(pack[0], 6)

    def test_packed_integer_invalid(self):
        pack = beets.mediafile.Packed("blah", beets.mediafile.packing.SLASHED)
        self.assertEqual(pack[0], 0)

    def test_packed_index_out_of_range(self):
        pack = beets.mediafile.Packed("06", beets.mediafile.packing.SLASHED)
        self.assertEqual(pack[1], 0)

    def test_safe_cast_string_to_int(self):
        self.assertEqual(_sc(int, 'something'), 0)

    def test_safe_cast_int_string_to_int(self):
        self.assertEqual(_sc(int, '20'), 20)

    def test_safe_cast_string_to_bool(self):
        self.assertEqual(_sc(bool, 'whatever'), False)

    def test_safe_cast_intstring_to_bool(self):
        self.assertEqual(_sc(bool, '5'), True)

    def test_safe_cast_string_to_float(self):
        self.assertAlmostEqual(_sc(float, '1.234'), 1.234)

    def test_safe_cast_int_to_float(self):
        self.assertAlmostEqual(_sc(float, 2), 2.0)

    def test_safe_cast_string_with_cruft_to_float(self):
        self.assertAlmostEqual(_sc(float, '1.234stuff'), 1.234)

    def test_safe_cast_negative_string_to_float(self):
        self.assertAlmostEqual(_sc(float, '-1.234'), -1.234)

class SafetyTest(unittest.TestCase):
    def _exccheck(self, fn, exc, data=''):
        fn = os.path.join(_common.RSRC, fn)
        with open(fn, 'w') as f:
            f.write(data)
        try:
            self.assertRaises(exc, beets.mediafile.MediaFile, fn)
        finally:
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

    def test_invalid_ogg_header_raises_unreadablefileerror(self):
        self._exccheck('corrupt.ogg', beets.mediafile.UnreadableFileError,
                       'OggS\x01vorbis')
    
    def test_corrupt_monkeys_raises_unreadablefileerror(self):
        self._exccheck('corrupt.ape', beets.mediafile.UnreadableFileError)
    
    def test_invalid_extension_raises_filetypeerror(self):
        self._exccheck('something.unknown', beets.mediafile.FileTypeError)

    def test_magic_xml_raises_unreadablefileerror(self):
        self._exccheck('nothing.xml', beets.mediafile.UnreadableFileError,
                       "ftyp")

    def test_broken_symlink(self):
        fn = os.path.join(_common.RSRC, 'brokenlink')
        os.symlink('does_not_exist', fn)
        try:
            self.assertRaises(beets.mediafile.UnreadableFileError,
                              beets.mediafile.MediaFile, fn)
        finally:
            os.unlink(fn)

class SideEffectsTest(unittest.TestCase):
    def setUp(self):
        self.empty = os.path.join(_common.RSRC, 'empty.mp3')

    def test_opening_tagless_file_leaves_untouched(self):
        old_mtime = os.stat(self.empty).st_mtime
        beets.mediafile.MediaFile(self.empty)
        new_mtime = os.stat(self.empty).st_mtime
        self.assertEqual(old_mtime, new_mtime)

class EncodingTest(unittest.TestCase):
    def setUp(self):
        src = os.path.join(_common.RSRC, 'full.m4a')
        self.path = os.path.join(_common.RSRC, 'test.m4a')
        shutil.copy(src, self.path)

        self.mf = beets.mediafile.MediaFile(self.path)

    def tearDown(self):
        os.remove(self.path)

    def test_unicode_label_in_m4a(self):
        self.mf.label = u'foo\xe8bar'
        self.mf.save()
        new_mf = beets.mediafile.MediaFile(self.path)
        self.assertEqual(new_mf.label, u'foo\xe8bar')

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
