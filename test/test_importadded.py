# This file is part of beets.
# Copyright 2015, Stig Inge Lea Bjornsen.
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

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

"""Tests for the `importadded` plugin."""

import os

from test._common import unittest
from test.test_importer import ImportHelper, AutotagStub
from beets import importer
from beets import util
from beetsplug.importadded import ImportAddedPlugin

_listeners = ImportAddedPlugin.listeners


def preserve_plugin_listeners():
    """Preserve the initial plugin listeners as they would otherwise be
    deleted after the first setup / tear down cycle.
    """
    if not ImportAddedPlugin.listeners:
        ImportAddedPlugin.listeners = _listeners


def modify_mtimes(paths, offset=-60000):
    for i, path in enumerate(paths, start=1):
        mstat = os.stat(path)
        os.utime(path, (mstat.st_atime, mstat.st_mtime + offset * i))


class ImportAddedTest(unittest.TestCase, ImportHelper):

    # The minimum mtime of the files to be imported
    min_mtime = None

    def setUp(self):
        preserve_plugin_listeners()
        self.setup_beets()
        self.load_plugins('importadded')
        self._create_import_dir(2)
        # Different mtimes on the files to be imported in order to test the
        # plugin
        modify_mtimes((mfile.path for mfile in self.media_files))
        self.min_mtime = min(os.path.getmtime(mfile.path)
                             for mfile in self.media_files)
        self.matcher = AutotagStub().install()
        self.matcher.macthin = AutotagStub.GOOD
        self._setup_import_session()
        self.importer.add_choice(importer.action.APPLY)

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()
        self.matcher.restore()

    def findMediaFile(self, item):
        """Find the pre-import MediaFile for an Item"""
        for m in self.media_files:
            if m.title.replace('Tag', 'Applied') == item.title:
                return m
        raise AssertionError("No MediaFile found for Item " +
                             util.displayable_path(item.path))

    def assertEqualTimes(self, first, second, msg=None):
        """For comparing file modification times at a sufficient precision"""
        self.assertAlmostEqual(first, second, places=4, msg=msg)

    def assertAlbumImport(self):
        self.importer.run()
        album = self.lib.albums().get()
        self.assertEqual(album.added, self.min_mtime)
        for item in album.items():
            self.assertEqual(item.added, self.min_mtime)

    def test_import_album_with_added_dates(self):
        self.assertAlbumImport()

    def test_import_album_inplace_with_added_dates(self):
        self.config['import']['copy'] = False
        self.config['import']['move'] = False
        self.config['import']['link'] = False
        self.assertAlbumImport()

    def test_import_album_with_preserved_mtimes(self):
        self.config['importadded']['preserve_mtimes'] = True
        self.importer.run()
        album = self.lib.albums().get()
        self.assertEqual(album.added, self.min_mtime)
        for item in album.items():
            self.assertEqualTimes(item.added, self.min_mtime)
            mediafile_mtime = os.path.getmtime(self.findMediaFile(item).path)
            self.assertEqualTimes(item.mtime, mediafile_mtime)
            self.assertEqualTimes(os.path.getmtime(item.path),
                                  mediafile_mtime)

    def test_reimported_album_skipped(self):
        # Import and record the original added dates
        self.importer.run()
        album = self.lib.albums().get()
        album_added_before = album.added
        items_added_before = dict((item.path, item.added)
                                  for item in album.items())
        # Newer Item path mtimes as if Beets had modified them
        modify_mtimes(items_added_before.keys(), offset=10000)
        # Reimport
        self._setup_import_session(import_dir=album.path)
        self.importer.run()
        # Verify the reimported items
        album = self.lib.albums().get()
        self.assertEqualTimes(album.added, album_added_before)
        items_added_after = dict((item.path, item.added)
                                 for item in album.items())
        for item_path, added_after in items_added_after.iteritems():
            self.assertEqualTimes(items_added_before[item_path], added_after,
                                  "reimport modified Item.added for " +
                                  item_path)

    def test_import_singletons_with_added_dates(self):
        self.config['import']['singletons'] = True
        self.importer.run()
        for item in self.lib.items():
            mfile = self.findMediaFile(item)
            self.assertEqualTimes(item.added, os.path.getmtime(mfile.path))

    def test_import_singletons_with_preserved_mtimes(self):
        self.config['import']['singletons'] = True
        self.config['importadded']['preserve_mtimes'] = True
        self.importer.run()
        for item in self.lib.items():
            mediafile_mtime = os.path.getmtime(self.findMediaFile(item).path)
            self.assertEqualTimes(item.added, mediafile_mtime)
            self.assertEqualTimes(item.mtime, mediafile_mtime)
            self.assertEqualTimes(os.path.getmtime(item.path),
                                  mediafile_mtime)

    def test_reimported_singletons_skipped(self):
        self.config['import']['singletons'] = True
        # Import and record the original added dates
        self.importer.run()
        items_added_before = dict((item.path, item.added)
                                  for item in self.lib.items())
        # Newer Item path mtimes as if Beets had modified them
        modify_mtimes(items_added_before.keys(), offset=10000)
        # Reimport
        import_dir = os.path.dirname(items_added_before.keys()[0])
        self._setup_import_session(import_dir=import_dir, singletons=True)
        self.importer.run()
        # Verify the reimported items
        items_added_after = dict((item.path, item.added)
                                 for item in self.lib.items())
        for item_path, added_after in items_added_after.iteritems():
            self.assertEqualTimes(items_added_before[item_path], added_after,
                                  "reimport modified Item.added for " +
                                  item_path)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
