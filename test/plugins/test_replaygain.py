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


from abc import ABC, abstractmethod
from typing import Any, ClassVar

import pytest
from mediafile import MediaFile

from beets.test.helper import (
    AsIsImporterMixin,
    ImportHelper,
    PluginMixin,
    has_program,
)
from beetsplug.replaygain import (
    FatalGstreamerPluginReplayGainError,
    GStreamerBackend,
)

try:
    import gi

    gi.require_version("Gst", "1.0")
    GST_AVAILABLE = True
except (ImportError, ValueError):
    GST_AVAILABLE = False


GAIN_PROG = next(
    (
        cmd
        for cmd in ["mp3gain", "mp3rgain", "aacgain"]
        if has_program(cmd, ["-v"])
    ),
    None,
)

FFMPEG_AVAILABLE = has_program("ffmpeg", ["-version"])


def reset_replaygain(item):
    item["rg_track_peak"] = None
    item["rg_track_gain"] = None
    item["rg_album_gain"] = None
    item["rg_album_gain"] = None
    item["r128_track_gain"] = None
    item["r128_album_gain"] = None
    item.write()
    item.store()


class ReplayGainPluginHelper(PluginMixin, ImportHelper):
    db_on_disk = True
    plugin = "replaygain"
    preload_plugin = False

    plugin_config: ClassVar[dict[str, Any]]

    @property
    def backend(self):
        return self.plugin_config["backend"]

    def setup_beets(self):
        # Implemented by Mixins, see above. This may decide to skip the test.
        self.test_backend()

        super().setup_beets()
        self.config["replaygain"].set(self.plugin_config)

        self.load_plugins()


class ThreadedImportMixin:
    def setup_beets(self):
        super().setup_beets()
        self.config["threaded"] = True


class BackendMixin(ABC):
    plugin_config: ClassVar[dict[str, Any]]
    has_r128_support: bool

    @abstractmethod
    def test_backend(self):
        """Check whether the backend actually has all required functionality."""


class GstBackendMixin(BackendMixin):
    plugin_config: ClassVar[dict[str, Any]] = {"backend": "gstreamer"}
    has_r128_support = True

    def test_backend(self):
        """Check whether the backend actually has all required functionality."""
        try:
            # Check if required plugins can be loaded by instantiating a
            # GStreamerBackend (via its .__init__).
            self.config["replaygain"]["targetlevel"] = 89
            GStreamerBackend(self.config["replaygain"], None)
        except FatalGstreamerPluginReplayGainError as e:
            # Skip the test if plugins could not be loaded.
            pytest.skip(str(e))


class CmdBackendMixin(BackendMixin):
    plugin_config: ClassVar[dict[str, Any]] = {
        "backend": "command",
        "command": GAIN_PROG,
    }
    has_r128_support = False


class FfmpegBackendMixin(BackendMixin):
    plugin_config: ClassVar[dict[str, Any]] = {"backend": "ffmpeg"}
    has_r128_support = True


class ReplayGainCliTest:
    FNAME: str

    def _add_album(self, *args, **kwargs):
        # Use a file with non-zero volume (most test assets are total silence)
        album = self.add_album_fixture(*args, fname=self.FNAME, **kwargs)
        for item in album.items():
            reset_replaygain(item)

        return album

    def test_cli_saves_track_gain(self):
        self._add_album(2)

        for item in self.lib.items():
            assert item.rg_track_peak is None
            assert item.rg_track_gain is None
            mediafile = MediaFile(item.path)
            assert mediafile.rg_track_peak is None
            assert mediafile.rg_track_gain is None

        self.run_command("replaygain")

        # Skip the test if rg_track_peak and rg_track gain is None, assuming
        # that it could only happen if the decoder plugins are missing.
        if all(
            i.rg_track_peak is None and i.rg_track_gain is None
            for i in self.lib.items()
        ):
            pytest.skip("decoder plugins could not be loaded.")

        for item in self.lib.items():
            assert item.rg_track_peak is not None
            assert item.rg_track_gain is not None
            mediafile = MediaFile(item.path)
            assert mediafile.rg_track_peak == pytest.approx(
                item.rg_track_peak, abs=1e-6
            )
            assert mediafile.rg_track_gain == pytest.approx(
                item.rg_track_gain, abs=1e-2
            )

    def test_cli_skips_calculated_tracks(self):
        album_rg = self._add_album(1)
        item_rg = album_rg.items()[0]

        if self.has_r128_support:
            album_r128 = self._add_album(1, ext="opus")
            item_r128 = album_r128.items()[0]

        self.run_command("replaygain")

        item_rg.load()
        assert item_rg.rg_track_gain is not None
        assert item_rg.rg_track_peak is not None
        assert item_rg.r128_track_gain is None

        item_rg.rg_track_gain += 1.0
        item_rg.rg_track_peak += 1.0
        item_rg.store()
        rg_track_gain = item_rg.rg_track_gain
        rg_track_peak = item_rg.rg_track_peak

        if self.has_r128_support:
            item_r128.load()
            assert item_r128.r128_track_gain is not None
            assert item_r128.rg_track_gain is None
            assert item_r128.rg_track_peak is None

            item_r128.r128_track_gain += 1.0
            item_r128.store()
            r128_track_gain = item_r128.r128_track_gain

        self.run_command("replaygain")

        item_rg.load()
        assert item_rg.rg_track_gain == rg_track_gain
        assert item_rg.rg_track_peak == rg_track_peak

        if self.has_r128_support:
            item_r128.load()
            assert item_r128.r128_track_gain == r128_track_gain

    def test_cli_does_not_skip_wrong_tag_type(self):
        """Check that items that have tags of the wrong type won't be skipped."""
        if not self.has_r128_support:
            # This test is a lot less interesting if the backend cannot write
            # both tag types.
            pytest.skip(
                f"r128 tags for opus not supported on backend {self.backend}"
            )

        album_rg = self._add_album(1)
        item_rg = album_rg.items()[0]

        album_r128 = self._add_album(1, ext="opus")
        item_r128 = album_r128.items()[0]

        item_rg.r128_track_gain = 0.0
        item_rg.store()

        item_r128.rg_track_gain = 0.0
        item_r128.rg_track_peak = 42.0
        item_r128.store()

        self.run_command("replaygain")
        item_rg.load()
        item_r128.load()

        assert item_rg.rg_track_gain is not None
        assert item_rg.rg_track_peak is not None
        # FIXME: Should the plugin null this field?
        # assert item_rg.r128_track_gain is None

        assert item_r128.r128_track_gain is not None
        # FIXME: Should the plugin null these fields?
        # assert item_r128.rg_track_gain is None
        # assert item_r128.rg_track_peak is None

    def test_cli_saves_album_gain_to_file(self):
        self._add_album(2)

        for item in self.lib.items():
            mediafile = MediaFile(item.path)
            assert mediafile.rg_album_peak is None
            assert mediafile.rg_album_gain is None

        self.run_command("replaygain", "-a")

        peaks = []
        gains = []
        for item in self.lib.items():
            mediafile = MediaFile(item.path)
            peaks.append(mediafile.rg_album_peak)
            gains.append(mediafile.rg_album_gain)

        # Make sure they are all the same
        assert max(peaks) == min(peaks)
        assert max(gains) == min(gains)

        assert max(gains) != 0.0
        assert max(peaks) != 0.0

    def test_cli_writes_only_r128_tags(self):
        if not self.has_r128_support:
            pytest.skip(
                f"r128 tags for opus not supported on backend {self.backend}"
            )

        album = self._add_album(2, ext="opus")

        self.run_command("replaygain", "-a")

        for item in album.items():
            mediafile = MediaFile(item.path)
            # does not write REPLAYGAIN_* tags
            assert mediafile.rg_track_gain is None
            assert mediafile.rg_album_gain is None
            # writes R128_* tags
            assert mediafile.r128_track_gain is not None
            assert mediafile.r128_album_gain is not None

    def test_targetlevel_has_effect(self):
        album = self._add_album(1)
        item = album.items()[0]

        def analyse(target_level):
            self.config["replaygain"]["targetlevel"] = target_level
            self.run_command("replaygain", "-f")
            item.load()
            return item.rg_track_gain

        gain_relative_to_84 = analyse(84)
        gain_relative_to_89 = analyse(89)

        assert gain_relative_to_84 != gain_relative_to_89

    def test_r128_targetlevel_has_effect(self):
        if not self.has_r128_support:
            pytest.skip(
                f"r128 tags for opus not supported on backend {self.backend}"
            )

        album = self._add_album(1, ext="opus")
        item = album.items()[0]

        def analyse(target_level):
            self.config["replaygain"]["r128_targetlevel"] = target_level
            self.run_command("replaygain", "-f")
            item.load()
            return item.r128_track_gain

        gain_relative_to_84 = analyse(84)
        gain_relative_to_89 = analyse(89)

        assert gain_relative_to_84 != gain_relative_to_89

    def test_per_disc(self):
        # Use the per_disc option and add a little more concurrency.
        album = self._add_album(track_count=4, disc_count=3)
        self.config["replaygain"]["per_disc"] = True
        self.run_command("replaygain", "-a")

        # FIXME: Add fixtures with known track/album gain (within a suitable
        # tolerance) so that we can actually check per-disc operation here.
        for item in album.items():
            assert item.rg_track_gain is not None
            assert item.rg_album_gain is not None

    def test_clears_wrong_tag_type(self):
        """Check that items that have tags of the wrong type won't be skipped."""
        if not self.has_r128_support:
            pytest.skip(
                f"r128 tags for opus not supported on backend {self.backend}"
            )

        album_rg = self._add_album(1)
        item_rg = album_rg.items()[0]

        album_r128 = self._add_album(1, ext="opus")
        item_r128 = album_r128.items()[0]

        item_r128.r128_track_gain = 0.0
        item_r128.store()

        item_rg.rg_track_gain = 0.0
        item_rg.rg_track_peak = 42.0
        item_rg.store()

        self.run_command("replaygain")
        item_rg.load()
        item_r128.load()

        assert item_rg.rg_track_gain is not None
        assert item_rg.rg_track_peak is not None
        assert item_rg.r128_track_gain is None

        assert item_r128.r128_track_gain is not None
        assert item_r128.rg_track_gain is None
        assert item_r128.rg_track_peak is None


@pytest.mark.skipif(not GST_AVAILABLE, reason="gstreamer cannot be found")
class TestReplayGainGstCli(
    ReplayGainCliTest, ReplayGainPluginHelper, GstBackendMixin
):
    FNAME = "full"  # file contains only silence


@pytest.mark.skipif(not GAIN_PROG, reason="no *gain command found")
class TestReplayGainCmdCli(
    ReplayGainCliTest, ReplayGainPluginHelper, CmdBackendMixin
):
    FNAME = "full"  # file contains only silence


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg cannot be found")
class TestReplayGainFfmpegCli(
    ReplayGainCliTest, ReplayGainPluginHelper, FfmpegBackendMixin
):
    FNAME = "full"  # file contains only silence


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg cannot be found")
class TestReplayGainFfmpegNoiseCli(
    ReplayGainCliTest, ReplayGainPluginHelper, FfmpegBackendMixin
):
    FNAME = "whitenoise"


class ImportTest(AsIsImporterMixin):
    def test_import_converted(self):
        self.run_asis_importer()
        for item in self.lib.items():
            # FIXME: Add fixtures with known track/album gain (within a
            # suitable tolerance) so that we can actually check correct
            # operation here.
            assert item.rg_track_gain is not None
            assert item.rg_album_gain is not None


@pytest.mark.skipif(not GST_AVAILABLE, reason="gstreamer cannot be found")
class TestReplayGainGstImport(
    ImportTest, ReplayGainPluginHelper, GstBackendMixin
):
    pass


@pytest.mark.skipif(not GAIN_PROG, reason="no *gain command found")
class TestReplayGainCmdImport(
    ImportTest, ReplayGainPluginHelper, CmdBackendMixin
):
    pass


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg cannot be found")
class TestReplayGainFfmpegImport(
    ImportTest, ReplayGainPluginHelper, FfmpegBackendMixin
):
    pass


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg cannot be found")
class TestReplayGainFfmpegThreadedImport(
    ThreadedImportMixin, ImportTest, ReplayGainPluginHelper, FfmpegBackendMixin
):
    pass
