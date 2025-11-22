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

"""Aid in submitting information to MusicBrainz.

This plugin allows the user to print track information in a format that is
parseable by the MusicBrainz track parser [1]. Programmatic submitting is not
implemented by MusicBrainz yet.

[1] https://wiki.musicbrainz.org/History:How_To_Parse_Track_Listings
"""

import subprocess

from beets import ui
from beets.autotag import Recommendation
from beets.plugins import BeetsPlugin
from beets.ui.commands.import_.session import PromptChoice
from beets.util import displayable_path
from beetsplug.info import print_data


class MBSubmitPlugin(BeetsPlugin):
    def __init__(self):
        super().__init__()

        self.config.add(
            {
                "format": "$track. $title - $artist ($length)",
                "threshold": "medium",
                "picard_path": "picard",
            }
        )

        # Validate and store threshold.
        self.threshold = self.config["threshold"].as_choice(
            {
                "none": Recommendation.none,
                "low": Recommendation.low,
                "medium": Recommendation.medium,
                "strong": Recommendation.strong,
            }
        )

        self.register_listener(
            "before_choose_candidate", self.before_choose_candidate_event
        )

    def before_choose_candidate_event(self, session, task):
        if task.rec <= self.threshold:
            return [
                PromptChoice("p", "Print tracks", self.print_tracks),
                PromptChoice("o", "Open files with Picard", self.picard),
            ]

    def picard(self, session, task):
        paths = []
        for p in task.paths:
            paths.append(displayable_path(p))
        try:
            picard_path = self.config["picard_path"].as_str()
            subprocess.Popen([picard_path] + paths)
            self._log.info("launched picard from\n{}", picard_path)
        except OSError as exc:
            self._log.error("Could not open picard, got error:\n{}", exc)

    def print_tracks(self, session, task):
        for i in sorted(task.items, key=lambda i: i.track):
            print_data(None, i, self.config["format"].as_str())

    def commands(self):
        """Add beet UI commands for mbsubmit."""
        mbsubmit_cmd = ui.Subcommand(
            "mbsubmit", help="Submit Tracks to MusicBrainz"
        )

        def func(lib, opts, args):
            items = lib.items(args)
            self._mbsubmit(items)

        mbsubmit_cmd.func = func

        return [mbsubmit_cmd]

    def _mbsubmit(self, items):
        """Print track information to be submitted to MusicBrainz."""
        for i in sorted(items, key=lambda i: i.track):
            print_data(None, i, self.config["format"].as_str())
