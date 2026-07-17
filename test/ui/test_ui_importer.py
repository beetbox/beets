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
        self.importer.io.addinput("m")
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
            self.importer.io.addinput("m")
            self.importer.io.addinput("1")
            self.importer.io.addinput("a")
            self.importer.run()
            album = self.lib.albums().get()
            assert "IDAlbum" in album.album


class ImportTrackDuplicateResolutionTest(
    TerminalImportMixin, test_importer.ImportTrackDuplicateResolutionTest
):
    """Run the per-track duplicate tests through ``TerminalImportSession``.

    Also covers the interactive ``ask`` prompt, which the non-terminal
    fixture cannot exercise.
    """

    def test_ask_prompt_skip(self):
        self.add_item_fixture(artist="Tag Artist", title="Tag Track 1")

        self.io.addinput("s")
        self._import(action="ask")

        # Answered "skip": the duplicate track is dropped, the other imported.
        assert len(self.lib.albums()) == 1
        assert {i.title for i in self.lib.items()} == {
            "Tag Track 1",
            "Tag Track 2",
        }

    def test_ask_prompt_remove(self):
        old = self.add_item_fixture(artist="Tag Artist", title="Tag Track 1")

        self.io.addinput("r")
        self._import(action="ask")

        # Answered "remove": the old library item (and file) is removed.
        assert not old.filepath.exists()
        assert sorted(i.title for i in self.lib.items()) == [
            "Tag Track 1",
            "Tag Track 2",
        ]

    def test_ask_prompt_keep(self):
        self.add_item_fixture(artist="Tag Artist", title="Tag Track 1")

        self.io.addinput("k")
        self._import(action="ask")

        # Answered "keep": nothing dropped or removed.
        assert len(self.lib.items()) == 3

    def test_ask_prompt_select_per_track(self):
        # Import a three-track album where tracks 1 and 2 duplicate existing
        # singletons; answer "sElect per track", then skip the first duplicate
        # and keep the second.
        self.prepare_album_for_import(3)
        self.add_item_fixture(artist="Tag Artist", title="Tag Track 1")
        self.add_item_fixture(artist="Tag Artist", title="Tag Track 2")

        self.io.addinput("e")  # select per track
        self.io.addinput("s")  # Tag Track 1: skip new
        self.io.addinput("k")  # Tag Track 2: keep all
        self._import(action="ask")

        titles = sorted(i.title for i in self.lib.items())
        # Track 1 was skipped (old singleton remains), track 2 kept (both
        # copies), track 3 imported.
        assert titles == [
            "Tag Track 1",
            "Tag Track 2",
            "Tag Track 2",
            "Tag Track 3",
        ]


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
