# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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

"""Shows file metadata.
"""

import os

from beets.plugins import BeetsPlugin
from beets import ui
from beets import mediafile
from beets import util


def info(paths):
    # Set up fields to output.
    fields = list(mediafile.MediaFile.fields())
    fields.remove('art')
    fields.remove('images')

    # Line format.
    other_fields = ['album art']
    maxwidth = max(len(name) for name in fields + other_fields)
    lineformat = u'{{0:>{0}}}: {{1}}'.format(maxwidth)

    first = True
    for path in paths:
        if not first:
            ui.print_()

        path = util.normpath(path)
        if not os.path.isfile(path):
            ui.print_(u'not a file: {0}'.format(
                util.displayable_path(path)
            ))
            continue
        ui.print_(path)
        try:
            mf = mediafile.MediaFile(path)
        except mediafile.UnreadableFileError:
            ui.print_('cannot read file: {0}'.format(
                util.displayable_path(path)
            ))
            continue

        # Basic fields.
        for name in fields:
            ui.print_(lineformat.format(name, getattr(mf, name)))
        # Extra stuff.
        ui.print_(lineformat.format('album art', mf.art is not None))

        first = False


class InfoPlugin(BeetsPlugin):

    def commands(self):
        cmd = ui.Subcommand('info', help='show file metadata')

        def func(lib, opts, args):
            if not args:
                raise ui.UserError('no file specified')
            info(args)
        cmd.func = func
        return [cmd]
