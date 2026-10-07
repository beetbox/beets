from types import SimpleNamespace

from beets.library import Item
from beets.test.helper import (
    AutotagImportTestCase,
    PluginMixin,
    TerminalImportMixin,
)
from beetsplug.mbsubmit import MBSubmitPlugin


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

    def _overlapping_multidisc_items(self):
        """Items with overlapping track numbers, intentionally out of order."""
        return [
            Item(disc=2, track=1, title="D2T1", artist="A", length=1),
            Item(disc=1, track=2, title="D1T2", artist="A", length=1),
            Item(disc=2, track=2, title="D2T2", artist="A", length=1),
            Item(disc=1, track=1, title="D1T1", artist="A", length=1),
        ]

    def test_mbsubmit_sorts_by_disc_then_track(self):
        """Multi-disc albums with overlapping track numbers print disc-grouped."""
        self.io.getoutput()  # clear prior output
        MBSubmitPlugin()._mbsubmit(self._overlapping_multidisc_items())
        assert self.io.getoutput() == (
            "01. D1T1 - A (0:01)\n"
            "02. D1T2 - A (0:01)\n"
            "01. D2T1 - A (0:01)\n"
            "02. D2T2 - A (0:01)\n"
        )

    def test_print_tracks_sorts_by_disc_then_track(self):
        """Importer Print tracks choice uses the same disc-then-track order."""
        self.io.getoutput()  # clear prior output
        task = SimpleNamespace(items=self._overlapping_multidisc_items())
        MBSubmitPlugin().print_tracks(session=None, task=task)
        assert self.io.getoutput() == (
            "01. D1T1 - A (0:01)\n"
            "02. D1T2 - A (0:01)\n"
            "01. D2T1 - A (0:01)\n"
            "02. D2T2 - A (0:01)\n"
        )
