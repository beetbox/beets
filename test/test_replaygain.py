# This file is part of beets.
# Copyright 2013, Thomas Scholtes
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


import os
import tempfile
import shutil
from glob import glob

import _common
from _common import unittest

import beets
from beets import ui
from beets import plugins
from beets.library import Item, Album
from beets.mediafile import MediaFile


class ReplayGainGstCliTest(unittest.TestCase):

    def setUp(self):
        self.setupBeets()
        self.config['replaygain']['backend'] = u'gstreamer'
        self.config['plugins'] = ['replaygain']
        self.setupLibrary(2)

    def tearDown(self):
        del os.environ['BEETSDIR']
        shutil.rmtree(self.temp_dir)
        self.config.clear()
        self.config.read(user=False)
        plugins._classes = set()
        plugins._instances = {}

    def setupBeets(self):
        self.temp_dir = tempfile.mkdtemp()
        os.environ['BEETSDIR'] = self.temp_dir

        self.config = beets.config
        self.config.clear()
        self.config.read(user=False)

        self.config['verbose'] = True
        self.config['color'] = False
        self.config['threaded'] = False
        self.config['import']['copy'] = False

        self.libdir = os.path.join(self.temp_dir, 'libdir')
        os.mkdir(self.libdir)
        self.config['directory'] = self.libdir

        self.libpath = os.path.join(self.temp_dir, 'lib')
        self.config['library'] = self.libpath

        self.lib = beets.library.Library(self.config['library'].as_filename(),
                                         self.libdir)

    def setupLibrary(self, file_count):
        """Add an album to the library with ``file_count`` items.
        """
        album = Album(id=1)
        album.add(self.lib)

        fixture_glob = os.path.join(_common.RSRC, '*.mp3')
        for src in glob(fixture_glob)[0:file_count]:
            dst = os.path.join(self.libdir, os.path.basename(src))
            shutil.copy(src, dst)
            item = Item.from_path(dst)
            item.album_id = 1
            item.add(self.lib)
            self._reset_replaygain(item)

    def _reset_replaygain(self, item):
        item['rg_track_peak'] = 0
        item['rg_track_gain'] = 0
        item['rg_album_gain'] = 0
        item['rg_album_gain'] = 0
        item.write()
        item.store()

    def test_cli_saves_track_gain(self):
        for item in self.lib.items():
            self.assertEqual(item.rg_track_peak, 0.0)
            self.assertEqual(item.rg_track_gain, 0.0)
            mediafile = MediaFile(item.path)
            self.assertEqual(mediafile.rg_track_peak, 0.0)
            self.assertEqual(mediafile.rg_track_gain, 0.0)

        ui._raw_main(['replaygain'])
        for item in self.lib.items():
            self.assertNotEqual(item.rg_track_peak, 0.0)
            self.assertNotEqual(item.rg_track_gain, 0.0)
            mediafile = MediaFile(item.path)
            self.assertAlmostEqual(
                mediafile.rg_track_peak, item.rg_track_peak, places=6)
            self.assertAlmostEqual(
                mediafile.rg_track_gain, item.rg_track_gain, places=6)

    def test_cli_skips_calculated_tracks(self):
        ui._raw_main(['replaygain'])
        item = self.lib.items()[0]
        peak = item.rg_track_peak
        item.rg_track_gain = 0.0
        ui._raw_main(['replaygain'])
        self.assertEqual(item.rg_track_gain, 0.0)
        self.assertEqual(item.rg_track_peak, peak)



    def test_cli_saves_album_gain_to_file(self):
        for item in self.lib.items():
            mediafile = MediaFile(item.path)
            self.assertEqual(mediafile.rg_album_peak, 0.0)
            self.assertEqual(mediafile.rg_album_gain, 0.0)

        ui._raw_main(['replaygain', '-a'])

        peaks = []
        gains = []
        for item in self.lib.items():
            mediafile = MediaFile(item.path)
            peaks.append(mediafile.rg_album_peak)
            gains.append(mediafile.rg_album_gain)

        # Make sure they are all the same
        self.assertEqual(max(peaks), min(peaks))
        self.assertEqual(max(gains), min(gains))

        self.assertNotEqual(max(gains), 0.0)
        self.assertNotEqual(max(peaks), 0.0)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
