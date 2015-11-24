# -*- coding: utf-8 -*-
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
from beets.library import Item
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
        # create a temporary Item to take advantage of __format__
        tags['item'] = Item(db=None, **tags)

        return tags

    return emitter


def library_data(lib, args):
    for item in lib.items(args):
        yield library_data_emitter(item)


def library_data_emitter(item):
    def emitter():
        data = dict(item.formatted())
        data['path'] = displayable_path(item.path)
        data['item'] = item
        return data
    return emitter


def update_summary(summary, tags):
    for key, value in tags.iteritems():
        if key not in summary:
            summary[key] = value
        elif summary[key] != value:
            summary[key] = '[various]'
    return summary


def print_data(data, fmt=None, human_length=True):
    """Print, with optional formatting, the fields of a single item.

    If no format string `fmt` is passed, the entries on `data` are printed one
    in each line, with the format 'field: value'. If `fmt` is not `None`, the
    item is printed according to `fmt`, using the `Item.__format__` machinery.

    If `raw_length` is `True`, the `length` field is displayed using its raw
    value (float with the number of seconds and miliseconds). If not, a human
    readable form is displayed instead (mm:ss).
    """
    item = data.pop('item', None)
    if fmt:
        # use fmt specified by the user, prettifying length if needed
        if human_length and '$length' in fmt:
            item['humanlength'] = ui.human_seconds_short(item.length)
            fmt = fmt.replace('$length', '$humanlength')
        ui.print_(format(item, fmt))
        return

    path = data.pop('path', None)
    formatted = {}
    for key, value in data.iteritems():
        if isinstance(value, list):
            formatted[key] = u'; '.join(value)
        if value is not None:
            if human_length and key == 'length':
                formatted[key] = ui.human_seconds_short(float(value))
            else:
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
        cmd.parser.add_option('-r', '--raw-length', action='store_true',
                              default=False,
                              help='display length as seconds')
        cmd.parser.add_format_option(target='item')
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
            except (mediafile.UnreadableFileError, IOError) as ex:
                self._log.error(u'cannot read file: {0}', ex)
                continue

            path = data.get('path')
            item = data.get('item')
            data = key_filter(data)
            data['path'] = path  # always show path
            data['item'] = item  # always include item, to avoid filtering
            if opts.summarize:
                update_summary(summary, data)
            else:
                if not first:
                    ui.print_()
                print_data(data, opts.format, not opts.raw_length)
                first = False

        if opts.summarize:
            print_data(summary, human_length=not opts.raw_length)


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

    def filter_(data):
        filtered = dict()
        for key, value in data.items():
            if any(map(lambda m: m.match(key), matchers)):
                filtered[key] = value
        return filtered

    return filter_


def identity(val):
    return val
