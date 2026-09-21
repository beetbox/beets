import mutagen.mp4
from mediafile import MediaFile

from beets.test import _common
from beets.test.helper import AsIsImporterMixin, ImportHelper, PluginMixin
from beets.util import syspath
from beetsplug.scrub import ScrubPlugin


class TestScrubbedImport(AsIsImporterMixin, PluginMixin, ImportHelper):
    db_on_disk = True
    plugin = "scrub"

    def test_tags_not_scrubbed(self):
        with self.configure_plugin({"auto": False}):
            self.run_asis_importer(write=True)

        for item in self.lib.items():
            imported_file = MediaFile(item.filepath)
            assert imported_file.artist == "Tag Artist"
            assert imported_file.album == "Tag Album"

    def test_tags_restored(self):
        with self.configure_plugin({"auto": True}):
            self.run_asis_importer(write=True)

        for item in self.lib.items():
            imported_file = MediaFile(item.filepath)
            assert imported_file.artist == "Tag Artist"
            assert imported_file.album == "Tag Album"

    def test_tags_not_scrubbed_when_nowrite(self):
        """When --nowrite is passed, scrubbing should be skipped entirely."""
        with self.configure_plugin({"auto": True}):
            self.run_asis_importer(write=False)

        for item in self.lib.items():
            imported_file = MediaFile(item.filepath)
            assert imported_file.artist == "Tag Artist"
            assert imported_file.album == "Tag Album"

    def test_illegal_mp4_art_does_not_crash_restore(self):
        """Non-JPEG/PNG MP4 cover art must not abort a scrub restore.

        mediafile can extract those images but cannot write them back,
        which used to raise ValueError and kill the whole import (#2498).
        """
        item = self.add_item_fixture(format="M4A")
        tiff = (_common.RSRC / "image-2x3.tiff").read_bytes()
        mp4 = mutagen.mp4.MP4(syspath(item.path))
        mp4["covr"] = [
            mutagen.mp4.MP4Cover(tiff, mutagen.mp4.MP4Cover.FORMAT_PNG)
        ]
        mp4.save()

        mf = MediaFile(item.filepath)
        assert mf.images
        assert mf.images[0].mime_type not in ("image/jpeg", "image/png")

        ScrubPlugin()._scrub_item(item, True)

        restored = MediaFile(item.filepath)
        assert restored.title == item.title
