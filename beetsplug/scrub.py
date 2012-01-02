# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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

"""Cleans extraneous metadata from files' tags via a command or
automatically whenever tags are written.
"""
from __future__ import with_statement

import logging

from beets.plugins import BeetsPlugin
from beets import ui
from beets import mediafile
from beets import util

log = logging.getLogger('beets')

AUTOSCRUB_KEY = 'autoscrub'

scrubbing = False

options = {
    AUTOSCRUB_KEY: True,
}
class ScrubPlugin(BeetsPlugin):
    """Removes extraneous metadata from files' tags."""
    def configure(self, config):
        options[AUTOSCRUB_KEY] = \
            ui.config_val(config, 'scrub', AUTOSCRUB_KEY, True, bool)

    def commands(self):
        def scrub_func(lib, config, opts, args):
            # This is a little bit hacky, but we set a global flag to
            # avoid autoscrubbing when we're also explicitly scrubbing.
            global scrubbing
            scrubbing = True

            # Walk through matching files and remove tags.
            for item in lib.items(ui.decargs(args)):
                log.info(u'scrubbing: %s' % util.displayable_path(item.path))
                mf = mediafile.MediaFile(item.path)
                _scrub(mf)
                mf.save()

                if opts.write:
                    log.debug(u'writing new tags after scrub')
                    item.write()

            scrubbing = False

        scrub_cmd = ui.Subcommand('scrub', help='clean audio tags')
        scrub_cmd.parser.add_option('-W', '--nowrite', dest='write',
                                    action='store_false', default=True,
                                    help='leave tags empty')
        scrub_cmd.func = scrub_func

        return [scrub_cmd]

def _scrub(mf):
    """Remove all tags from a MediaFile by manipulating the underlying
    Mutagen object.
    """
    mf.mgfile.delete()
    # Reinitialize the MediaFile: also a little hacky.
    mf.__init__(mf.path)

# Automatically embed art into imported albums.
@ScrubPlugin.listen('write')
def write_item(item, mf):
    if not scrubbing and options[AUTOSCRUB_KEY]:
        log.debug(u'auto-scrubbing %s' % util.displayable_path(item.path))
        _scrub(mf)
