# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Matt Lichtenberg.
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

"""Creates freedesktop.org-compliant .directory files on an album level.
"""

from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets import ui


class FreedesktopPlugin(BeetsPlugin):
    def commands(self):
        deprecated = ui.Subcommand(
            "freedesktop",
            help=u"Print a message to redirect to thumbnails --dolphin")
        deprecated.func = self.deprecation_message
        return [deprecated]

    def deprecation_message(self, lib, opts, args):
        ui.print_(u"This plugin is deprecated. Its functionality is "
                  u"superseded by the 'thumbnails' plugin")
        ui.print_(u"'thumbnails --dolphin' replaces freedesktop. See doc & "
                  u"changelog for more information")
