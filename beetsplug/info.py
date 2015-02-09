# This file is part of beets.
# Copyright 2015, Adrian Sampson.
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

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import os
import re

from beets.plugins import BeetsPlugin
from beets import ui
from beets import mediafile
from beets.util import displayable_path, normpath, syspath


def tag_data(lib, args):
    query = []
    for arg in args:
        path = normpath(arg)
        if os.path.isfile(syspath(path)):
            yield tag_data_emitter(path)
        else:
            query.append(arg)

    if query:
        for item in lib.items(query):
            yield tag_data_emitter(item.path)


def tag_data_emitter(path):
    def emitter():
        fields = list(mediafile.MediaFile.readable_fields())
        fields.remove('images')
        mf = mediafile.MediaFile(syspath(path))
        tags = {}
        for field in fields:
            tags[field] = getattr(mf, field)
        tags['art'] = mf.art is not None
        tags['path'] = displayable_path(path)
        return tags
    return emitter


def library_data(lib, args):
    for item in lib.items(args):
        yield library_data_emitter(item)


def library_data_emitter(item):
    def emitter():
        data = dict(item.formatted())
        data['path'] = displayable_path(item.path)
        return data
    return emitter


def update_summary(summary, tags):
    for key, value in tags.iteritems():
        if key not in summary:
            summary[key] = value
        elif summary[key] != value:
            summary[key] = '[various]'
    return summary


def print_data(data):
    path = data.pop('path', None)
    formatted = {}
    for key, value in data.iteritems():
        if isinstance(value, list):
            formatted[key] = u'; '.join(value)
        if value is not None:
            formatted[key] = value

    if len(formatted) == 0:
        return

    maxwidth = max(len(key) for key in formatted)
    lineformat = u'{{0:>{0}}}: {{1}}'.format(maxwidth)

    if path:
        ui.print_(displayable_path(path))

    for field in sorted(formatted):
        value = formatted[field]
        if isinstance(value, list):
            value = u'; '.join(value)
        ui.print_(lineformat.format(field, value))


class InfoPlugin(BeetsPlugin):

    def commands(self):
        cmd = ui.Subcommand('info', help='show file metadata')
        cmd.func = self.run
        cmd.parser.add_option('-l', '--library', action='store_true',
                              help='show library fields instead of tags')
        cmd.parser.add_option('-s', '--summarize', action='store_true',
                              help='summarize the tags of all files')
        cmd.parser.add_option('-i', '--include-keys', default=[],
                              action='append', dest='included_keys',
                              help='comma separated list of keys to show')
        return [cmd]

    def run(self, lib, opts, args):
        """Print tag info or library data for each file referenced by args.

        Main entry point for the `beet info ARGS...` command.

        If an argument is a path pointing to an existing file, then the tags
        of that file are printed. All other arguments are considered
        queries, and for each item matching all those queries the tags from
        the file are printed.

        If `opts.summarize` is true, the function merges all tags into one
        dictionary and only prints that. If two files have different values
        for the same tag, the value is set to '[various]'
        """
        if opts.library:
            data_collector = library_data
        else:
            data_collector = tag_data

        included_keys = []
        for keys in opts.included_keys:
            included_keys.extend(keys.split(','))
        key_filter = make_key_filter(included_keys)

        first = True
        summary = {}
        for data_emitter in data_collector(lib, ui.decargs(args)):
            try:
                data = data_emitter()
            except mediafile.UnreadableFileError as ex:
                self._log.error(u'cannot read file: {0}', ex)
                continue

            path = data.get('path')
            data = key_filter(data)
            data['path'] = path  # always show path
            if opts.summarize:
                update_summary(summary, data)
            else:
                if not first:
                    ui.print_()
                print_data(data)
                first = False

        if opts.summarize:
            print_data(summary)


def make_key_filter(include):
    """Return a function that filters a dictionary.

    The returned filter takes a dictionary and returns another
    dictionary that only includes the key-value pairs where the key
    glob-matches one of the keys in `include`.
    """
    if not include:
        return identity

    matchers = []
    for key in include:
        key = re.escape(key)
        key = key.replace(r'\*', '.*')
        matchers.append(re.compile(key + '$'))

    def filter(data):
        filtered = dict()
        for key, value in data.items():
            if any(map(lambda m: m.match(key), matchers)):
                filtered[key] = value
        return filtered

    return filter


def identity(val):
    return val
