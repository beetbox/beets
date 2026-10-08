from types import SimpleNamespace

from beets import plugins
from beets.autotag import Recommendation
from beets.test.helper import (
    AutotagImportTestCase,
    PluginMixin,
    TerminalImportMixin,
)


class MBSubmitPluginTest(
    PluginMixin, TerminalImportMixin, AutotagImportTestCase
):
    plugin = "mbsubmit"

    def setUp(self):
        super().setUp()
        self.prepare_album_for_import(2)
        self.setup_importer()

    def test_print_tracks_output(self):
        """Test the output of the "print tracks" choice."""
        self.io.addinput("p")
        self.io.addinput("s")
        # Print tracks; Skip
        self.importer.run()

        # Manually build the string for comparing the output.
        tracklist = (
            "Open files with Picard? "
            "01. Tag Track 1 - Tag Artist (0:01)\n"
            "02. Tag Track 2 - Tag Artist (0:01)"
        )
        assert tracklist in self.io.getoutput()

    def test_print_tracks_output_as_tracks(self):
        """Test the output of the "print tracks" choice, as singletons."""
        self.io.addinput("t")
        self.io.addinput("s")
        self.io.addinput("p")
        self.io.addinput("s")
        # as Tracks; Skip; Print tracks; Skip
        self.importer.run()

        # Manually build the string for comparing the output.
        tracklist = (
            "Open files with Picard? 02. Tag Track 2 - Tag Artist (0:01)"
        )
        assert tracklist in self.io.getoutput()

    def test_choices_offered_with_no_recommendation(self):
        """Prompt choices must appear even when the recommendation is none."""
        task = SimpleNamespace(rec=Recommendation.none)
        results = plugins.send(
            "before_choose_candidate", session=None, task=task
        )
        shorts = [c.short for choices in results for c in choices]
        assert shorts == ["p", "o"]

    def test_no_choices_offered_above_threshold(self):
        """Prompt choices should not appear when recommendation is above threshold."""
        task = SimpleNamespace(rec=Recommendation.strong)
        results = plugins.send(
            "before_choose_candidate", session=None, task=task
        )
        shorts = [c.short for choices in results for c in choices]
        assert shorts == []
