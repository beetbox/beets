from unittest.mock import patch

import pytest

from beets.test.helper import ImportHelper, PluginTestHelper

pytestmark = pytest.mark.requires_import("librosa")


class TestAutoBPMPlugin(ImportHelper, PluginTestHelper):
    plugin = "autobpm"

    @pytest.fixture
    def item(self):
        return self.add_item_fixture()

    @pytest.fixture
    def beat_track_spy(self):
        import librosa

        with patch(
            "librosa.beat.beat_track", wraps=librosa.beat.beat_track
        ) as spy:
            yield spy

    @pytest.fixture
    def importer(self):
        self.import_media = []
        self.prepare_album_for_import(1)
        track = self.import_media[0]
        track.bpm = None
        track.save()
        return self.setup_importer(autotag=False)

    def test_command(self, item):
        item.bpm = None
        item.store()
        self.run_command("autobpm")

        item.load()
        assert item.bpm == 117

    def test_command_force(self, item):
        item.bpm = 10
        item.store()

        self.run_command("autobpm")
        item.load()
        assert item.bpm == 10

        self.run_command("autobpm", "--force")
        item.load()
        assert item.bpm == 117

    def test_command_overwrite(self, item):
        item.bpm = 10
        item.store()

        self.unload_plugins()
        self.config[self.plugin]["overwrite"] = True
        self.load_plugins()

        self.run_command("autobpm")
        item.load()
        assert item.bpm == 117

    def test_command_quiet(self, item, caplog):
        item.bpm = 10
        item.store()

        with caplog.at_level("DEBUG"):
            self.run_command("autobpm", "--quiet")
        assert not any("already exists" in msg for msg in caplog.messages)

        with caplog.at_level("DEBUG"):
            self.run_command("autobpm")
        assert any("already exists" in msg for msg in caplog.messages)

    def test_command_start_bpm(self, item, beat_track_spy):
        item.bpm = None
        item.store()

        self.run_command("autobpm", "--start-bpm", "155")

        assert beat_track_spy.call_args.kwargs["start_bpm"] == 155

    def test_command_start_bpm_overrides_config(self, item, beat_track_spy):
        item.bpm = None
        item.store()

        self.unload_plugins()
        self.config[self.plugin]["beat_track_kwargs"] = {
            "start_bpm": 100,
            "tightness": 100,
        }
        self.load_plugins()

        self.run_command("autobpm", "-b", "155")

        kwargs = beat_track_spy.call_args.kwargs
        assert kwargs["start_bpm"] == 155
        assert kwargs["tightness"] == 100

    def test_import(self, importer):
        importer.run()

        assert self.lib.items().get().bpm == 117
