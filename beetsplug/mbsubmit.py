# -*- coding: utf-8 -*-
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

[1] http://wiki.musicbrainz.org/History:How_To_Parse_Track_Listings
"""

from __future__ import division, absolute_import, print_function


from beets.autotag import Recommendation
from beets.plugins import BeetsPlugin
from beets.ui.commands import PromptChoice
from beetsplug.info import print_data


class MBSubmitPlugin(BeetsPlugin):
    def __init__(self):
        super(MBSubmitPlugin, self).__init__()

        self.config.add({
            'format': u'$track. $title - $artist ($length)',
            'threshold': 'medium',
        })

        # Validate and store threshold.
        self.threshold = self.config['threshold'].as_choice({
            'none': Recommendation.none,
            'low': Recommendation.low,
            'medium': Recommendation.medium,
            'strong': Recommendation.strong
        })

        self.register_listener('before_choose_candidate',
                               self.before_choose_candidate_event)

    def before_choose_candidate_event(self, session, task):
        if task.rec <= self.threshold:
            return [PromptChoice(u'p', u'Print tracks', self.print_tracks)]

    def print_tracks(self, session, task):
        for i in sorted(task.items, key=lambda i: i.track):
            print_data(None, i, self.config['format'].as_str())
