from unittest.mock import patch

import mutagen.flac
from mediafile import MediaFile

from beets.test import _common
from beets.test.helper import AsIsImporterMixin, ImportHelper, PluginMixin


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


class TestScrubbedFlacImport(AsIsImporterMixin, PluginMixin, ImportHelper):
    """Scrubbing a FLAC must not cost a rewrite of the audio stream."""

    db_on_disk = True
    plugin = "scrub"
    resource_path = _common.RSRC / "full.flac"

    def test_padding_not_stripped(self):
        """Scrubbing must never save the file with its padding removed.

        FLAC reserves a padding block so that metadata can be rewritten in
        place. `mutagen.flac.FLAC.delete()` saves with ``padding=lambda x: 0``,
        which drops it: the file shrinks, and writing the tags back then has to
        grow it again. That is two rewrites of the whole audio stream for every
        track, which dominates the cost of an import on network storage.

        The end state cannot tell the two apart -- writing the tags back
        restores a padding block either way -- so this checks what is asked of
        every save along the way.
        """

        class DummyInfo:
            padding = 4096
            size = 1024

            def get_default_padding(self):
                return 1024

        original = mutagen.flac.FLAC._save
        requested = []

        def spy(self, filething, metadata_blocks, deleteid3, padding=None):
            if callable(padding):
                requested.append(padding(DummyInfo()))
            return original(
                self, filething, metadata_blocks, deleteid3, padding
            )

        with patch.object(mutagen.flac.FLAC, "_save", spy):
            with self.configure_plugin({"auto": True}):
                self.run_asis_importer(write=True)

        assert 0 not in requested, (
            "scrub saved the file with its padding stripped, forcing a "
            "rewrite of the audio stream"
        )

    def test_tags_restored(self):
        with self.configure_plugin({"auto": True}):
            self.run_asis_importer(write=True)

        for item in self.lib.items():
            imported_file = MediaFile(item.filepath)
            assert imported_file.artist == "Tag Artist"
            assert imported_file.album == "Tag Album"


class ArtPreservedMixin(AsIsImporterMixin, PluginMixin, ImportHelper):
    """Embedded art must survive a scrub, in every format.

    MP3 and Ogg keep their pictures inside the tag block that scrubbing
    empties, so the art has to be read before and written back after. FLAC
    stores them in blocks of their own and is the one format where getting
    this wrong is invisible -- hence the three subclasses below.
    """

    db_on_disk = True
    plugin = "scrub"

    def test_art_preserved(self):
        with self.configure_plugin({"auto": True}):
            self.run_asis_importer(write=True)

        for item in self.lib.items():
            assert MediaFile(item.filepath).images, (
                f"scrubbing dropped the embedded art from {item.filepath}"
            )


class TestScrubbedArtFlac(ArtPreservedMixin):
    resource_path = _common.RSRC / "image.flac"


class TestScrubbedArtMp3(ArtPreservedMixin):
    resource_path = _common.RSRC / "image.mp3"


class TestScrubbedArtOgg(ArtPreservedMixin):
    resource_path = _common.RSRC / "image.ogg"
