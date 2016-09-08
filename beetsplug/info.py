# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

from __future__ import division, absolute_import, print_function

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
        # create a temporary Item to take advantage of __format__
        item = Item.from_path(syspath(path))

        return tags, item
    return emitter


def library_data(lib, args):
    for item in lib.items(args):
        yield library_data_emitter(item)


def library_data_emitter(item):
    def emitter():
        data = dict(item.formatted())
        data.pop('path', None)  # path is fetched from item

        return data, item
    return emitter


def update_summary(summary, tags):
    for key, value in tags.items():
        if key not in summary:
            summary[key] = value
        elif summary[key] != value:
            summary[key] = '[various]'
    return summary


def print_data(data, item=None, fmt=None):
    """Print, with optional formatting, the fields of a single element.

    If no format string `fmt` is passed, the entries on `data` are printed one
    in each line, with the format 'field: value'. If `fmt` is not `None`, the
    `item` is printed according to `fmt`, using the `Item.__format__`
    machinery.
    """
    if fmt:
        # use fmt specified by the user
        ui.print_(format(item, fmt))
        return

    path = displayable_path(item.path) if item else None
    formatted = {}
    for key, value in data.items():
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


def print_data_keys(data, item=None):
    """Print only the keys (field names) for an item.
    """
    path = displayable_path(item.path) if item else None
    formatted = []
    for key, value in data.items():
        formatted.append(key)

    if len(formatted) == 0:
        return

    line_format = u'{0}{{0}}'.format(u' ' * 4)
    if path:
        ui.print_(displayable_path(path))

    for field in sorted(formatted):
        ui.print_(line_format.format(field))


class InfoPlugin(BeetsPlugin):

    def commands(self):
        cmd = ui.Subcommand('info', help=u'show file metadata')
        cmd.func = self.run
        cmd.parser.add_option(
            u'-l', u'--library', action='store_true',
            help=u'show library fields instead of tags',
        )
        cmd.parser.add_option(
            u'-s', u'--summarize', action='store_true',
            help=u'summarize the tags of all files',
        )
        cmd.parser.add_option(
            u'-i', u'--include-keys', default=[],
            action='append', dest='included_keys',
            help=u'comma separated list of keys to show',
        )
        cmd.parser.add_option(
            u'-k', u'--keys-only', action='store_true',
            help=u'show only the keys',
        )
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
                data, item = data_emitter()
            except (mediafile.UnreadableFileError, IOError) as ex:
                self._log.error(u'cannot read file: {0}', ex)
                continue

            data = key_filter(data)
            if opts.summarize:
                update_summary(summary, data)
            else:
                if not first:
                    ui.print_()
                if opts.keys_only:
                    print_data_keys(data, item)
                else:
                    fmt = ui.decargs([opts.format])[0] if opts.format else None
                    print_data(data, item, fmt)
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

    def filter_(data):
        filtered = dict()
        for key, value in data.items():
            if any([m.match(key) for m in matchers]):
                filtered[key] = value
        return filtered

    return filter_


def identity(val):
    return val
