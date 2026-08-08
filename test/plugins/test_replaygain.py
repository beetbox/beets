import queue
import shutil
import sys
import threading
import time
from typing import Any, ClassVar

import pytest
from mediafile import MediaFile

from beets.library import Item
from beets.test.helper import (
    RUNNING_IN_CI,
    AsIsImporterMixin,
    ImportHelper,
    PluginMixin,
)
from beetsplug.replaygain import ExceptionWatcher, MetaflacBackend, RgTask

try:
    import gi

    gi.require_version("Gst", "1.0")
    GST_AVAILABLE = True
except (ImportError, ValueError):
    GST_AVAILABLE = False


GAIN_PROG = next(
    (cmd for cmd in ["mp3gain", "mp3rgain", "aacgain"] if shutil.which(cmd)),
    None,
)

SKIP_FFMPEG = pytest.mark.skipif(
    not shutil.which("ffmpeg") and not RUNNING_IN_CI,
    reason="ffmpeg cannot be found and not running in CI",
)
SKIP_GSTREAMER = pytest.mark.skipif(
    not GST_AVAILABLE and not RUNNING_IN_CI,
    reason="gstreamer cannot be found and not running in CI",
)
XFAIL_GSTREAMER_WIN_PY315 = pytest.mark.xfail(
    sys.platform == "win32" and sys.version_info >= (3, 15),
    reason="gstreamer-bundle does not support Python 3.15 on Windows yet",
    strict=True,
)
SKIP_METAFLAC = pytest.mark.skipif(
    (
        not shutil.which("metaflac")  # included in ``flac`` package
        and not RUNNING_IN_CI
    ),
    reason="no metaflac command found and not running in CI",
)
SKIP_GAIN = pytest.mark.skipif(
    not GAIN_PROG and not RUNNING_IN_CI,
    reason="no *gain command found and not running in CI",
)


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
        super().setup_beets()
        self.config["replaygain"].set(self.plugin_config)

        self.load_plugins()


class ThreadedImportMixin:
    def setup_beets(self):
        super().setup_beets()
        self.config["threaded"] = True


class BackendMixin:
    plugin_config: ClassVar[dict[str, Any]]


class GstBackendMixin(BackendMixin):
    plugin_config: ClassVar[dict[str, Any]] = {"backend": "gstreamer"}


class CmdBackendMixin(BackendMixin):
    plugin_config: ClassVar[dict[str, Any]] = {
        "backend": "command",
        "command": GAIN_PROG,
    }


class FfmpegBackendMixin(BackendMixin):
    plugin_config: ClassVar[dict[str, Any]] = {"backend": "ffmpeg"}


class R128Test:
    def test_cli_does_not_skip_wrong_tag_type(self):
        """Check that items that have tags of the wrong type won't be skipped."""
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

    def test_cli_writes_only_r128_tags(self):
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

    def test_r128_targetlevel_has_effect(self):
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

    def test_r128_cli_skips_calculated_tracks(self):
        album_r128 = self._add_album(1, ext="opus")
        item_r128 = album_r128.items()[0]

        self.run_command("replaygain")

        item_r128.load()
        assert item_r128.r128_track_gain is not None
        assert item_r128.rg_track_gain is None
        assert item_r128.rg_track_peak is None

        item_r128.r128_track_gain += 1.0
        item_r128.store()
        r128_track_gain = item_r128.r128_track_gain

        self.run_command("replaygain")

        item_r128.load()
        assert item_r128.r128_track_gain == r128_track_gain

    def test_clears_wrong_tag_type(self):
        """Check that items that have tags of the wrong type won't be skipped."""
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


class MetaflacBackendMixin(BackendMixin):
    plugin_config: ClassVar[dict[str, Any]] = {"backend": "metaflac"}
    has_r128_support = False


class ReplayGainCliTest(ReplayGainPluginHelper):
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

        self.run_command("replaygain")

        item_rg.load()
        assert item_rg.rg_track_gain == rg_track_gain
        assert item_rg.rg_track_peak == rg_track_peak

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


@SKIP_GSTREAMER
@XFAIL_GSTREAMER_WIN_PY315
class TestReplayGainGstCli(R128Test, ReplayGainCliTest, GstBackendMixin):
    FNAME = "full"  # file contains only silence


@SKIP_GAIN
class TestReplayGainCmdCli(ReplayGainCliTest, CmdBackendMixin):
    FNAME = "full"  # file contains only silence


@SKIP_FFMPEG
class TestReplayGainFfmpegCli(R128Test, ReplayGainCliTest, FfmpegBackendMixin):
    FNAME = "full"  # file contains only silence


@SKIP_FFMPEG
class TestReplayGainFfmpegNoiseCli(
    R128Test, ReplayGainCliTest, FfmpegBackendMixin
):
    FNAME = "whitenoise"


@SKIP_METAFLAC
class TestReplayGainMetaflacCli(ReplayGainCliTest, MetaflacBackendMixin):
    FNAME = "whitenoise"

    def _add_album(self, *args, **kwargs):
        kwargs.setdefault("ext", "flac")
        return super()._add_album(*args, **kwargs)


def test_metaflac_backend_parses_output():
    output = (
        "01.flac: -1.234567 1.234567 1.987654 0.123456\n"
        "02.flac: -1.234567 1.234567 -1.987654 0.987654\n"
    )

    results = MetaflacBackend._parse_output(output)

    assert set(results) == {"01.flac", "02.flac"}

    album_gain_1, album_peak_1, track_gain_1, track_peak_1 = results["01.flac"]
    album_gain_2, album_peak_2, track_gain_2, track_peak_2 = results["02.flac"]

    # Album gain/peak is shared across every file in the batch...
    assert album_gain_1 == pytest.approx(album_gain_2)
    assert album_peak_1 == pytest.approx(album_peak_2)

    # ...but each file keeps its own distinct track gain/peak.
    assert track_gain_1 == pytest.approx(1.987654)
    assert track_peak_1 == pytest.approx(0.123456)

    assert track_gain_2 == pytest.approx(-1.987654)
    assert track_peak_2 == pytest.approx(0.987654)


def test_metaflac_backend_cannot_compute_album_gain_with_mixed_formats():
    backend = MetaflacBackend.__new__(MetaflacBackend)

    items = [Item(format="FLAC"), Item(format="MP3"), Item(format="FLAC")]
    task = RgTask(items, None, 89.0, None, "metaflac", None)

    result = backend.compute_album_gain(task)

    assert result.track_gains is None
    assert result.album_gain is None


class CountingQueue(queue.Queue[BaseException]):
    def __init__(self):
        super().__init__()
        self.get_calls = 0

    def get(self, *args, **kwargs):
        self.get_calls += 1
        return super().get(*args, **kwargs)

    def get_nowait(self):
        self.get_calls += 1
        return super().get_nowait()


class TestExceptionWatcher:
    def test_does_not_busy_wait(self):
        exc_queue = CountingQueue()
        watcher = ExceptionWatcher(exc_queue, lambda: None)
        watcher.start()
        time.sleep(0.5)
        watcher.join()

        assert not watcher.is_alive()
        # A blocking get wakes up a handful of times; a busy loop would call
        # it many thousands of times.
        assert exc_queue.get_calls < 50

    def test_runs_callback_on_exception(self, monkeypatch):
        raised = []
        monkeypatch.setattr(
            threading, "excepthook", lambda args: raised.append(args.exc_value)
        )
        callback_called = threading.Event()
        exc_queue = queue.Queue()
        watcher = ExceptionWatcher(exc_queue, callback_called.set)
        watcher.start()

        error = RuntimeError("worker failed")
        exc_queue.put(error)

        assert callback_called.wait(timeout=5)
        watcher.join(timeout=5)
        assert raised == [error]


class ImportTest(AsIsImporterMixin, ReplayGainPluginHelper):
    def test_import_converted(self):
        self.run_asis_importer()
        for item in self.lib.items():
            # FIXME: Add fixtures with known track/album gain (within a
            # suitable tolerance) so that we can actually check correct
            # operation here.
            assert item.rg_track_gain is not None
            assert item.rg_album_gain is not None


@SKIP_GSTREAMER
@XFAIL_GSTREAMER_WIN_PY315
class TestReplayGainGstImport(ImportTest, GstBackendMixin):
    pass


@SKIP_GAIN
class TestReplayGainCmdImport(ImportTest, CmdBackendMixin):
    pass


@SKIP_FFMPEG
class TestReplayGainFfmpegImport(ImportTest, FfmpegBackendMixin):
    pass


@SKIP_FFMPEG
class TestReplayGainFfmpegThreadedImport(
    ThreadedImportMixin, ImportTest, FfmpegBackendMixin
):
    pass
