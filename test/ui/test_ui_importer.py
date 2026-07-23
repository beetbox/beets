"""Tests the TerminalImportSession. The tests are the same as in the

test_importer module. But here the test importer inherits from
``TerminalImportSession``. So we test this class, too.
"""

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
    pass


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
    pass


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
