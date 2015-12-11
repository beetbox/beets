# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2015, Adrian Sampson and Diego Moreda.
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
parseable by the MusicBrainz track parser. Programmatic submitting is not
implemented by MusicBrainz yet.
"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)


from beets.autotag import Recommendation
from beets.importer import action
from beets.plugins import BeetsPlugin
from beets.ui.commands import ExtraChoice
from beetsplug.info import print_data


class MBSubmitPlugin(BeetsPlugin):
    def __init__(self):
        super(MBSubmitPlugin, self).__init__()

        self.register_listener('before_choose_candidate',
                               self.before_choose_candidate_event)

    def before_choose_candidate_event(self, session, task):
        # This intends to illustrate a simple plugin that adds choices
        # depending on conditions.
        # Plugins should return a list of ExtraChoices (basically, the
        # "cosmetic" values and a callback function). This list is received and
        # flattened on plugins.send('before_choose_candidate').
        if not task.candidates or task.rec == Recommendation.none:
            return [ExtraChoice(self, 'PRINT', 'Print tracks',
                                self.print_tracks),
                    ExtraChoice(self, 'PRINT_SKIP', 'print tracks and sKip',
                                self.print_tracks_and_skip)]

    # Callbacks for choices.
    def print_tracks(self, session, task):
        for i in task.items:
            print_data(None, i, '$track. $artist - $title ($length)')

    def print_tracks_and_skip(self, session, task):
        # Example of a function that automatically sets the next action,
        # avoiding the user to be prompted again. It has some drawbacks (for
        # example, actions such as action.MANUAL are not handled properly, as
        # they do not exit the main TerminalImportSession.choose_match loop).
        #
        # The idea is that if a callback function returns an action.X value,
        # task.action is set to that value after the callback is processed.
        for i in task.items:
            print_data(None, i, '$track. $artist - $title ($length)')
        return action.SKIP
