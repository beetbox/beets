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


class GroupAlbumsImportTest(
    TerminalImportMixin, test_importer.GroupAlbumsImportTest
):
    pass


class GlobalGroupAlbumsImportTest(
    TerminalImportMixin, test_importer.GlobalGroupAlbumsImportTest
):
    pass
