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
from beets import mediafile

TEST_TITLES = ('The Opener','The Second Track','The Last Track')
class NonAutotaggedImportTest(unittest.TestCase):
    def setUp(self):
        self.io = _common.DummyIO()
        #self.io.install()

        self.libdb = os.path.join(_common.RSRC, 'testlib.blb')
        self.lib = library.Library(self.libdb)
        self.libdir = os.path.join(_common.RSRC, 'testlibdir')
        self.lib.directory = self.libdir
        self.lib.path_formats = {
            'default': os.path.join('$artist', '$album', '$title')
        }

        self.srcdir = os.path.join(_common.RSRC, 'testsrcdir')

    def tearDown(self):
        self.io.restore()
        if os.path.exists(self.libdb):
            os.remove(self.libdb)
        if os.path.exists(self.libdir):
            shutil.rmtree(self.libdir)
        if os.path.exists(self.srcdir):
            shutil.rmtree(self.srcdir)

    def _create_test_file(self, filepath, metadata):
        """Creates an mp3 file at the given path within self.srcdir.
        filepath is given as an array of folder names, ending with the
        file name. Sets the file's metadata from the provided dict.
        Returns the full, real path to the file.
        """
        realpath = os.path.join(self.srcdir, *filepath)
        if not os.path.exists(os.path.dirname(realpath)):
            os.makedirs(os.path.dirname(realpath))
        shutil.copy(os.path.join(_common.RSRC, 'full.mp3'), realpath)

        f = mediafile.MediaFile(realpath)
        for attr in metadata:
            setattr(f, attr, metadata[attr])
        f.save()

        return realpath

    def _run_import(self, titles=TEST_TITLES, delete=False, threaded=False):
        # Make a bunch of tracks to import.
        paths = []
        for i, title in enumerate(titles):
            paths.append(self._create_test_file(
                ['the_album', 'track_%s.mp3' % (i+1)],
                {
                    'track': (i+1),
                    'artist': 'The Artist',
                    'album': 'The Album',
                    'title': title,
                }))

        # Run the UI "beet import" command!
        importer.run_import(
                lib=self.lib,
                paths=[os.path.dirname(paths[0])],
                copy=True,
                write=True,
                autot=False,
                logfile=None,
                art=False,
                threaded=threaded,
                color=False,
                delete=delete,
                quiet=True,
                resume=False,
                quiet_fallback='skip',
                choose_match_func = None,
                should_resume_func = None,
        )

        return paths

    def test_album_created_with_track_artist(self):
        self._run_import()
        albums = self.lib.albums()
        self.assertEqual(len(albums), 1)
        self.assertEqual(albums[0].albumartist, 'The Artist')

    def _copy_arrives(self):
        artist_folder = os.path.join(self.libdir, 'The Artist')
        album_folder = os.path.join(artist_folder, 'The Album')
        self.assertEqual(len(os.listdir(artist_folder)), 1)
        self.assertEqual(len(os.listdir(album_folder)), 3)

        filenames = set(os.listdir(album_folder))
        destinations = set('%s.mp3' % title for title in TEST_TITLES)
        self.assertEqual(filenames, destinations)
    def test_import_copy_arrives(self):
        self._run_import()
        self._copy_arrives()
    def test_threaded_import_copy_arrives(self):
        self._run_import(threaded=True)
        self._copy_arrives()

    def test_import_no_delete(self):
        paths = self._run_import(['sometrack'], delete=False)
        self.assertTrue(os.path.exists(paths[0]))

    def test_import_with_delete(self):
        paths = self._run_import(['sometrack'], delete=True)
        self.assertFalse(os.path.exists(paths[0]))

class ImportApplyTest(unittest.TestCase, _common.ExtraAsserts):
    def setUp(self):
        self.libdir = os.path.join(_common.RSRC, 'testlibdir')
        os.mkdir(self.libdir)
        self.lib = library.Library(':memory:', self.libdir)
        self.lib.path_formats = {
            'default': 'one',
            'comp': 'two',
            'singleton': 'three',
        }

        self.srcpath = os.path.join(self.libdir, 'srcfile.mp3')
        shutil.copy(os.path.join(_common.RSRC, 'full.mp3'), self.srcpath)
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
        task.is_album = True
        task.set_choice((info, items))
        coro.send(task)

    def _call_apply_choice(self, coro, items, choice):
        task = importer.ImportTask(None, None, items)
        task.is_album = True
        task.set_choice(choice)
        coro.send(task)

    def test_apply_no_delete(self):
        coro = importer.apply_choices(_common.iconfig(self.lib, delete=False))
        coro.next() # Prime coroutine.
        self._call_apply(coro, [self.i], self.info)
        self.assertExists(self.srcpath)

    def test_apply_with_delete(self):
        coro = importer.apply_choices(_common.iconfig(self.lib, delete=True))
        coro.next() # Prime coroutine.
        self._call_apply(coro, [self.i], self.info)
        self.assertNotExists(self.srcpath)

    def test_apply_asis_uses_album_path(self):
        coro = importer.apply_choices(_common.iconfig(self.lib))
        coro.next() # Prime coroutine.
        self._call_apply_choice(coro, [self.i], importer.action.ASIS)
        self.assertExists(
            os.path.join(self.libdir, self.lib.path_formats['default']+'.mp3')
        )

    def test_apply_match_uses_album_path(self):
        coro = importer.apply_choices(_common.iconfig(self.lib))
        coro.next() # Prime coroutine.
        self._call_apply(coro, [self.i], self.info)
        self.assertExists(
            os.path.join(self.libdir, self.lib.path_formats['default']+'.mp3')
        )

    def test_apply_as_tracks_uses_singleton_path(self):
        coro = importer.apply_choices(_common.iconfig(self.lib))
        coro.next() # Prime coroutine.
        self._call_apply_choice(coro, [self.i], importer.action.TRACKS)
        self.assertExists(
            os.path.join(self.libdir, self.lib.path_formats['singleton']+'.mp3')
        )

    def test_apply_sentinel(self):
        coro = importer.apply_choices(_common.iconfig(self.lib))
        coro.next()
        coro.send(importer.ImportTask.done_sentinel('toppath'))
        # Just test no exception for now.

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
