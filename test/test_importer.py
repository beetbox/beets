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

"""Tests for the general importer functionality.
"""
import unittest
import os
import shutil

import _common
from beets import library
from beets import importer

class ImportApplyTest(unittest.TestCase, _common.ExtraAsserts):
    def setUp(self):
        self.libdir = os.path.join('rsrc', 'testlibdir')
        os.mkdir(self.libdir)
        self.lib = library.Library(':memory:', self.libdir)
        self.lib.path_formats = {
            'default': 'one',
            'comp': 'two',
            'singleton': 'three',
        }

        self.srcpath = os.path.join(self.libdir, 'srcfile.mp3')
        shutil.copy(os.path.join('rsrc', 'full.mp3'), self.srcpath)
        self.i = library.Item.from_path(self.srcpath)
        self.i.comp = False

        trackinfo = {'title': 'one', 'artist': 'some artist',
                     'track': 1, 'length': 1, 'id': 'trackid'}
        self.info = {
            'artist': 'some artist',
            'album': 'some album',
            'tracks': [trackinfo],
            'va': False,
            'album_id': 'albumid',
            'artist_id': 'artistid',
            'albumtype': 'soundtrack',
        }

    def tearDown(self):
        shutil.rmtree(self.libdir)

    def _call_apply(self, coro, items, info):
        task = importer.ImportTask(None, None, None)
        task.set_choice((info, items))
        coro.send(task)

    def _call_apply_choice(self, coro, items, choice):
        task = importer.ImportTask(None, None, items)
        task.set_choice(choice)
        coro.send(task)

    def test_apply_no_delete(self):
        coro = importer.apply_choices(self.lib, True, False, False,
                                      False, False)
        coro.next() # Prime coroutine.
        self._call_apply(coro, [self.i], self.info)
        self.assertExists(self.srcpath)

    def test_apply_with_delete(self):
        coro = importer.apply_choices(self.lib, True, False, False,
                                      True, False)
        coro.next() # Prime coroutine.
        self._call_apply(coro, [self.i], self.info)
        self.assertNotExists(self.srcpath)

    def test_apply_asis_uses_album_path(self):
        coro = importer.apply_choices(self.lib, True, False, False,
                                      False, False)
        coro.next() # Prime coroutine.
        self._call_apply_choice(coro, [self.i], importer.CHOICE_ASIS)
        self.assertExists(
            os.path.join(self.libdir, self.lib.path_formats['default']+'.mp3')
        )

    def test_apply_match_uses_album_path(self):
        coro = importer.apply_choices(self.lib, True, False, False,
                                      False, False)
        coro.next() # Prime coroutine.
        self._call_apply(coro, [self.i], self.info)
        self.assertExists(
            os.path.join(self.libdir, self.lib.path_formats['default']+'.mp3')
        )

    def test_apply_as_tracks_uses_singleton_path(self):
        coro = importer.apply_choices(self.lib, True, False, False,
                                      False, False)
        coro.next() # Prime coroutine.
        self._call_apply_choice(coro, [self.i], importer.CHOICE_TRACKS)
        self.assertExists(
            os.path.join(self.libdir, self.lib.path_formats['singleton']+'.mp3')
        )

class DuplicateCheckTest(unittest.TestCase):
    def setUp(self):
        self.lib = library.Library(':memory:')
        self.i = _common.item()
        self.album = self.lib.add_album([self.i], True)

    def test_duplicate_album(self):
        res = importer._duplicate_check(self.lib, self.i.albumartist,
                                        self.i.album)
        self.assertTrue(res)

    def test_different_album(self):
        res = importer._duplicate_check(self.lib, 'xxx', 'yyy')
        self.assertFalse(res)

    def test_duplicate_va_album(self):
        self.album.albumartist = 'an album artist'
        res = importer._duplicate_check(self.lib, 'an album artist',
                                        self.i.album)
        self.assertTrue(res)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
