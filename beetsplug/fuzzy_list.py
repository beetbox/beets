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

"""Get a random song or album from the library.
"""
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, decargs, print_
from beets.util.functemplate import Template
import random
import difflib

def fuzzy_score(query, item):
    return difflib.SequenceMatcher(a=query, b=item).quick_ratio()

def is_match(query, item, album=False, verbose=False):
    query = ' '.join(query)

    if album: values = [item.albumartist, item.album]
    else: values = [item.artist, item.album, item.title]

    s =  max(fuzzy_score(query, i) for i in values)
    if s > 0.7: return (True, s) if verbose else True
    else: return (False, s) if verbose else False

def fuzzy_list(lib, config, opts, args):
    query = decargs(args)
    path = opts.path
    fmt = opts.format
    verbose = opts.verbose

    if fmt is None:
        # If no specific template is supplied, use a default
        if opts.album:
            fmt = u'$albumartist - $album'
        else:
            fmt = u'$artist - $album - $title'
    template = Template(fmt)

    if opts.album:
        objs = lib.albums()
    else:
        objs = lib.items()

    # matches = [i for i in objs if is_match(query, i)]

    if opts.album:
        for album in objs:
            if is_match(query, album, album=True):
                if path:
                    print_(album.item_dir())
                else:
                    print_(album.evaluate_template(template))
                if verbose: print is_match(query,album, album=True, verbose=True)[1]
    else:
        for item in objs:
            if is_match(query, item):
                if path:
                    print_(item.path)
                else:
                    print_(item.evaluate_template(template, lib))
                if verbose: print is_match(query,item, verbose=True)[1]

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
fuzzy_cmd.func = fuzzy_list



class Fuzzy(BeetsPlugin):
    def commands(self):
        return [fuzzy_cmd]
