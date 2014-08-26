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
from beets.util import displayable_path, normpath


def run(lib, opts, args):
    """Print tag info or library data for each file referenced by args.

    Main entry point for the `beet info ARGS...` command.
    """
    if opts.library:
        print_library_info(lib, args)
    else:
        print_tag_info(lib, args)


def print_tag_info(lib, args):
    """Print tag info for each file referenced by args.

    If an argument is a path pointing to an existing file, then the tags
    of that file are printed. All other arguments are considered
    queries, and for each item matching all those queries the tags from
    the file are printed.
    """
    if not args:
        raise ui.UserError('no file specified')

    paths = []
    query = []
    for arg in args:
        path = normpath(arg)
        if os.path.isfile(path):
            paths.append(path)
        else:
            query.append(arg)

    if query:
        for item in lib.items(query):
            paths.append(item.path)

    first = True
    for path in paths:
        if not first:
            ui.print_()
        try:
            data = tag_data(path)
        except mediafile.UnreadableFileError:
            ui.print_('cannot read file: {0}'.format(displayable_path(path)))
        else:
            print_data(path, data)
        first = False


def print_library_info(lib, queries):
    """Print library data for each item matching all queries
    """
    first = True
    for item in lib.items(queries):
        if not first:
            ui.print_()
        print_data(item.path, library_data(item))
        first = False


def tag_data(path):
    fields = list(mediafile.MediaFile.readable_fields())
    fields.remove('images')
    mf = mediafile.MediaFile(path)
    tags = {}
    for field in fields:
        tags[field] = getattr(mf, field)
    tags['art'] = mf.art is not None
    return tags


def library_data(item):
    return dict(item.formatted())


def print_data(path, data):
    maxwidth = max(len(key) for key in data)
    lineformat = u'{{0:>{0}}}: {{1}}'.format(maxwidth)

    ui.print_(displayable_path(path))

    for field in sorted(data):
        value = data[field]
        if isinstance(value, list):
            value = u'; '.join(value)
        ui.print_(lineformat.format(field, value))


class InfoPlugin(BeetsPlugin):

    def commands(self):
        cmd = ui.Subcommand('info', help='show file metadata')
        cmd.func = run
        cmd.parser.add_option('-l', '--library', action='store_true',
                              help='show library fields instead of tags')
        return [cmd]
