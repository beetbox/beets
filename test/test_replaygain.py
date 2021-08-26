# This file is part of beets.
# Copyright 2016, Thomas Scholtes
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


import unittest
from mediafile import MediaFile

from beets import config
from beetsplug.replaygain import (FatalGstreamerPluginReplayGainError,
                                  GStreamerBackend)
from test.helper import TestHelper, has_program

try:
    import gi
    gi.require_version('Gst', '1.0')
    GST_AVAILABLE = True
except (ImportError, ValueError):
    GST_AVAILABLE = False

if any(has_program(cmd, ['-v']) for cmd in ['mp3gain', 'aacgain']):
    GAIN_PROG_AVAILABLE = True
else:
    GAIN_PROG_AVAILABLE = False

FFMPEG_AVAILABLE = has_program('ffmpeg', ['-version'])


def reset_replaygain(item):
    item['rg_track_peak'] = None
    item['rg_track_gain'] = None
    item['rg_album_gain'] = None
    item['rg_album_gain'] = None
    item.write()
    item.store()
    item.store()
    item.store()


class ReplayGainCliTestBase(TestHelper):
    def setUp(self):
        self.setup_beets(disk=True)
        self.config['replaygain']['backend'] = self.backend

        try:
            self.load_plugins('replaygain')
        except Exception:
            import sys
            # store exception info so an error in teardown does not swallow it
            exc_info = sys.exc_info()
            try:
                self.teardown_beets()
                self.unload_plugins()
            except Exception:
                # if load_plugins() failed then setup is incomplete and
                # teardown operations may fail. In particular # {Item,Album}
                # may not have the _original_types attribute in unload_plugins
                pass
            raise None.with_traceback(exc_info[2])

        album = self.add_album_fixture(2)
        for item in album.items():
            reset_replaygain(item)

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def _reset_replaygain(self, item):
        item['rg_track_peak'] = None
        item['rg_track_gain'] = None
        item['rg_album_peak'] = None
        item['rg_album_gain'] = None
        item['r128_track_gain'] = None
        item['r128_album_gain'] = None
        item.write()
        item.store()

    def test_cli_saves_track_gain(self):
        for item in self.lib.items():
            self.assertIsNone(item.rg_track_peak)
            self.assertIsNone(item.rg_track_gain)
            mediafile = MediaFile(item.path)
            self.assertIsNone(mediafile.rg_track_peak)
            self.assertIsNone(mediafile.rg_track_gain)

        self.run_command('replaygain')

        # Skip the test if rg_track_peak and rg_track gain is None, assuming
        # that it could only happen if the decoder plugins are missing.
        if all(i.rg_track_peak is None and i.rg_track_gain is None
               for i in self.lib.items()):
            self.skipTest('decoder plugins could not be loaded.')

        for item in self.lib.items():
            self.assertIsNotNone(item.rg_track_peak)
            self.assertIsNotNone(item.rg_track_gain)
            mediafile = MediaFile(item.path)
            self.assertAlmostEqual(
                mediafile.rg_track_peak, item.rg_track_peak, places=6)
            self.assertAlmostEqual(
                mediafile.rg_track_gain, item.rg_track_gain, places=2)

    def test_cli_skips_calculated_tracks(self):
        self.run_command('replaygain')
        item = self.lib.items()[0]
        peak = item.rg_track_peak
        item.rg_track_gain = 0.0
        self.run_command('replaygain')
        self.assertEqual(item.rg_track_gain, 0.0)
        self.assertEqual(item.rg_track_peak, peak)

    def test_cli_saves_album_gain_to_file(self):
        for item in self.lib.items():
            mediafile = MediaFile(item.path)
            self.assertIsNone(mediafile.rg_album_peak)
            self.assertIsNone(mediafile.rg_album_gain)

        self.run_command('replaygain', '-a')

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

    def test_cli_writes_only_r128_tags(self):
        if self.backend == "command":
            # opus not supported by command backend
            return

        album = self.add_album_fixture(2, ext="opus")
        for item in album.items():
            self._reset_replaygain(item)

        self.run_command('replaygain', '-a')

        for item in album.items():
            mediafile = MediaFile(item.path)
            # does not write REPLAYGAIN_* tags
            self.assertIsNone(mediafile.rg_track_gain)
            self.assertIsNone(mediafile.rg_album_gain)
            # writes R128_* tags
            self.assertIsNotNone(mediafile.r128_track_gain)
            self.assertIsNotNone(mediafile.r128_album_gain)

    def test_target_level_has_effect(self):
        item = self.lib.items()[0]

        def analyse(target_level):
            self.config['replaygain']['targetlevel'] = target_level
            self._reset_replaygain(item)
            self.run_command('replaygain', '-f')
            mediafile = MediaFile(item.path)
            return mediafile.rg_track_gain

        gain_relative_to_84 = analyse(84)
        gain_relative_to_89 = analyse(89)

        # check that second calculation did work
        if gain_relative_to_84 is not None:
            self.assertIsNotNone(gain_relative_to_89)

        self.assertNotEqual(gain_relative_to_84, gain_relative_to_89)


@unittest.skipIf(not GST_AVAILABLE, 'gstreamer cannot be found')
class ReplayGainGstCliTest(ReplayGainCliTestBase, unittest.TestCase):
    backend = 'gstreamer'

    def setUp(self):
        try:
            # Check if required plugins can be loaded by instantiating a
            # GStreamerBackend (via its .__init__).
            config['replaygain']['targetlevel'] = 89
            GStreamerBackend(config['replaygain'], None)
        except FatalGstreamerPluginReplayGainError as e:
            # Skip the test if plugins could not be loaded.
            self.skipTest(str(e))

        super().setUp()


@unittest.skipIf(not GAIN_PROG_AVAILABLE, 'no *gain command found')
class ReplayGainCmdCliTest(ReplayGainCliTestBase, unittest.TestCase):
    backend = 'command'


@unittest.skipIf(not FFMPEG_AVAILABLE, 'ffmpeg cannot be found')
class ReplayGainFfmpegTest(ReplayGainCliTestBase, unittest.TestCase):
    backend = 'ffmpeg'


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
