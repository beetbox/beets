# This file is part of beets.
# Copyright 2016, Adrian Sampson and Diego Moreda.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.


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
