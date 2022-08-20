# This file is part of beets.
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

"""Deprecation warning for the removed gmusic plugin."""

from beets.plugins import BeetsPlugin


class Gmusic(BeetsPlugin):
    def __init__(self):
        super().__init__()

        self._log.warning("The 'gmusic' plugin has been removed following the"
                          " shutdown of Google Play Music. Remove the plugin"
                          " from your configuration to silence this warning.")
