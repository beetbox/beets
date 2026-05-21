import pytest

from beets.test.helper import ImportHelper, PluginMixin

pytestmark = pytest.mark.requires_import("librosa")


class TestAutoBPMPlugin(PluginMixin, ImportHelper):
    plugin = "autobpm"

    @pytest.fixture(scope="class", name="lib")
    def fixture_lib(self):
        self.setup_beets()

        yield self.lib

        self.teardown_beets()

    @pytest.fixture(scope="class")
    def item(self):
        return self.add_item_fixture()

    @pytest.fixture(scope="class")
    def importer(self, lib):
        self.import_media = []
        self.prepare_album_for_import(1)
        track = self.import_media[0]
        track.bpm = None
        track.save()
        return self.setup_importer(autotag=False)

    def test_command(self, lib, item):
        item.bpm = None
        item.store()
        self.run_command("autobpm", lib=lib)

        item.load()
        assert item.bpm == 117

    def test_command_force(self, lib, item):
        item.bpm = 10
        item.store()

        self.run_command("autobpm", lib=lib)
        item.load()
        assert item.bpm == 10

        self.run_command("autobpm", "--force", lib=lib)
        item.load()
        assert item.bpm == 117

    def test_command_overwrite(self, lib, item):
        item.bpm = 10
        item.store()

        self.unload_plugins()
        self.config[self.plugin]["overwrite"] = True
        self.load_plugins()

        self.run_command("autobpm", lib=lib)
        item.load()
        assert item.bpm == 117

    def test_command_quiet(self, lib, item, caplog):
        item.bpm = 10
        item.store()

        with caplog.at_level("DEBUG"):
            self.run_command("autobpm", "--quiet", lib=lib)
        assert not any("already exists" in msg for msg in caplog.messages)

        with caplog.at_level("DEBUG"):
            self.run_command("autobpm", lib=lib)
        assert any("already exists" in msg for msg in caplog.messages)

    def test_import(self, lib, importer):
        importer.run()

        assert lib.items().get().bpm == 117
