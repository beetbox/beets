import pytest
from mediafile import MediaFile

from beets.test.helper import AsIsImporterMixin, ImportHelper, PluginMixin
from beetsplug.scrub import _tag_matches_keep


@pytest.mark.parametrize(
    ("tag", "keep", "matches"),
    [
        ("TXXX:SUBBOX_ID", {"subbox_id"}, True),
        ("COMM:iTunNORM:eng", {"itunnorm"}, True),
        ("USLT:Lyrics:eng", {"lyrics"}, True),
        ("----:com.apple.iTunes:SUBBOX_ID", {"subbox_id"}, True),
        ("subbox_id", {"subbox_id"}, True),
        ("COMM:iTunNORM:eng", {"eng"}, False),
    ],
)
def test_tag_matches_keep(tag, keep, matches):
    assert _tag_matches_keep(tag, keep) is matches


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
