# This file is part of beets.
# Copyright 2011, Philippe Mongeau.
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

"""Like beet list, but with fuzzy matching
"""
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, decargs, print_obj
from beets.util.functemplate import Template
from beets import config
import difflib


def fuzzy_score(queryMatcher, item):
    queryMatcher.set_seq1(item)
    return queryMatcher.quick_ratio()


def is_match(queryMatcher, item, album=False, verbose=False, threshold=0.7):
    if album:
        values = [item.albumartist, item.album]
    else:
        values = [item.artist, item.album, item.title]

    s = max(fuzzy_score(queryMatcher, i.lower()) for i in values)
    if verbose:
        return (s >= threshold, s)
    else:
        return s >= threshold


def fuzzy_list(lib, opts, args):
    query = decargs(args)
    query = ' '.join(query).lower()
    queryMatcher = difflib.SequenceMatcher(b=query)

    if opts.threshold is not None:
        threshold = float(opts.threshold)
    else:
        threshold = config['fuzzy']['threshold'].as_number()

    if opts.path:
        fmt = '$path'
    else:
        fmt = opts.format
    template = Template(fmt) if fmt else None

    if opts.album:
        objs = lib.albums()
    else:
        objs = lib.items()

    items = filter(lambda i: is_match(queryMatcher, i, album=opts.album,
                                      threshold=threshold), objs)

    for item in items:
        print_obj(item, lib, template)
        if opts.verbose:
            print(is_match(queryMatcher, item,
                           album=opts.album, verbose=True)[1])


fuzzy_cmd = Subcommand('fuzzy',
                        help='list items using fuzzy matching')
fuzzy_cmd.parser.add_option('-a', '--album', action='store_true',
        help='choose an album instead of track')
fuzzy_cmd.parser.add_option('-p', '--path', action='store_true',
        help='print the path of the matched item')
fuzzy_cmd.parser.add_option('-f', '--format', action='store',
        help='print with custom format', default=None)
fuzzy_cmd.parser.add_option('-v', '--verbose', action='store_true',
        help='output scores for matches')
fuzzy_cmd.parser.add_option('-t', '--threshold', action='store',
        help='return result with a fuzzy score above threshold. \
              (default is 0.7)', default=None)
fuzzy_cmd.func = fuzzy_list


class Fuzzy(BeetsPlugin):
    def __init__(self):
        super(Fuzzy, self).__init__()
        self.config.add({
            'threshold': 0.7,
        })

    def commands(self):
        return [fuzzy_cmd]
