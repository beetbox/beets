import os

from mediafile import MediaFile

from beets.test.helper import AsIsImporterMixin, ImportTestCase, PluginMixin


class ScrubbedImportTest(AsIsImporterMixin, PluginMixin, ImportTestCase):
    db_on_disk = True
    plugin = "scrub"

    def test_tags_not_scrubbed(self):
        with self.configure_plugin({"auto": False}):
            self.run_asis_importer(write=True)

        for item in self.lib.items():
            imported_file = MediaFile(os.path.join(item.path))
            assert imported_file.artist == "Tag Artist"
            assert imported_file.album == "Tag Album"

    def test_tags_restored(self):
        with self.configure_plugin({"auto": True}):
            self.run_asis_importer(write=True)

        for item in self.lib.items():
            imported_file = MediaFile(os.path.join(item.path))
            assert imported_file.artist == "Tag Artist"
            assert imported_file.album == "Tag Album"

    def test_tags_not_restored(self):
        with self.configure_plugin({"auto": True}):
            self.run_asis_importer(write=False)

        for item in self.lib.items():
            imported_file = MediaFile(os.path.join(item.path))
            assert imported_file.artist is None
            assert imported_file.album is None
