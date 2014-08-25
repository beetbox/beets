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


def run(lib, opts, args):
    """Print tag info for each file referenced by args.

    Main entry point for the `beet info ARGS...` command.

    If an argument is a path pointing to an existing file, then the tags
    of that file are printed. All other arguments are considered
    queries, and for each item matching all those queries the tags from
    the file are printed.
    """
    paths, query = parse_args(args)

    first = True
    for path in paths:
        if not first:
            ui.print_()
        print_tags(path)
        first = False

    if not query:
        return

    for item in lib.items(*query):
        if not first:
            ui.print_()
        print_tags(item.path)
        first = False


def parse_args(args):
    """Split `args` into a tuple of paths and querys.
    """
    if not args:
        raise ui.UserError('no file specified')
    paths = []
    query = []
    for arg in args:
        if os.sep in arg and os.path.exists(arg):
            paths.append(util.normpath(arg))
        else:
            query.append(arg)
    return paths, query


def print_tags(path):
    # Set up fields to output.
    fields = list(mediafile.MediaFile.readable_fields())
    fields.remove('art')
    fields.remove('images')

    # Line format.
    other_fields = ['album art']
    maxwidth = max(len(name) for name in fields + other_fields)
    lineformat = u'{{0:>{0}}}: {{1}}'.format(maxwidth)

    ui.print_(path)
    try:
        mf = mediafile.MediaFile(path)
    except mediafile.UnreadableFileError:
        ui.print_('cannot read file: {0}'.format(
            util.displayable_path(path)
        ))
        return

    # Basic fields.
    for name in fields:
        ui.print_(lineformat.format(name, getattr(mf, name)))
    # Extra stuff.
    ui.print_(lineformat.format('album art', mf.art is not None))


class InfoPlugin(BeetsPlugin):

    def commands(self):
        cmd = ui.Subcommand('info', help='show file metadata')
        cmd.func = run
        return [cmd]
