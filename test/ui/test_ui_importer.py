"""Tests the TerminalImportSession. The tests are the same as in the

test_importer module. But here the test importer inherits from
``TerminalImportSession``. So we test this class, too.
"""

from unittest import mock

from beets import importer
from beets.test.helper import TerminalImportMixin
from test import test_importer


class TestNonAutotaggedImport(
    TerminalImportMixin, test_importer.TestNonAutotaggedImport
):
    pass


class TestImport(TerminalImportMixin, test_importer.TestImport):
    pass

class ImportSingletonTest(
    TerminalImportMixin, test_importer.ImportSingletonTest
):
    def test_singleton_manual_search_updates_candidates(self):
        self.importer.io.addinput("e")
        self.importer.io.addinput("ManualArtist")
        self.importer.io.addinput("ManualTrack")
        self.importer.io.addinput("a")
        self.importer.run()
        assert not self.lib.albums()
        assert self.lib.items().get().title == "ManualTrack"


class ImportTracksTest(TerminalImportMixin, test_importer.ImportTracksTest):
    pass


class ImportCompilationTest(
    TerminalImportMixin, test_importer.ImportCompilationTest
):
    pass


class ImportExistingTest(TerminalImportMixin, test_importer.ImportExistingTest):
    pass


class ChooseCandidateTest(
    TerminalImportMixin, test_importer.ChooseCandidateTest
):
    def test_manual_search_updates_candidates(self):
        self.importer.io.addinput("e")
        self.importer.io.addinput("ManualArtist")
        self.importer.io.addinput("ManualAlbum")
        self.importer.io.addinput("1")
        self.importer.io.addinput("a")
        self.importer.run()
        album = self.lib.albums().get()
        assert "ManualAlbum" in album.album

    def test_manual_id_updates_candidates(self):
        album_info = self.matcher._make_album_match("IDArtist", "IDAlbum", 1)
        with mock.patch(
            "beets.metadata_plugins.albums_for_ids", return_value=[album_info]
        ):
            self.importer.io.addinput("i")
            self.importer.io.addinput("custom_release_id")
            self.importer.io.addinput("1")
            self.importer.io.addinput("a")
            self.importer.run()
            album = self.lib.albums().get()
            assert "IDAlbum" in album.album


class GroupAlbumsImportTest(
    TerminalImportMixin, test_importer.GroupAlbumsImportTest
):
    pass


class GlobalGroupAlbumsImportTest(
    TerminalImportMixin, test_importer.GlobalGroupAlbumsImportTest
):
    pass


class TestImportDuplicateAlbumUpgrade(
    TerminalImportMixin, test_importer.TestImportDuplicateAlbumUpgrade
):
    def setup_beets(self):
        super().setup_beets()
        self.config["import"]["duplicate_action"] = "ask"
        self.importer.add_duplicate_action(importer.DuplicateAction.UPGRADE)
