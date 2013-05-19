# This file is part of beets.
# Copyright 2013, Philippe Mongeau.
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
from __future__ import absolute_import
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, decargs, print_obj
from beets.util.functemplate import Template
import random
from operator import attrgetter
from itertools import groupby
import collections

def random_item(lib, opts, args):
    query = decargs(args)
    if opts.path:
        fmt = '$path'
    else:
        fmt = opts.format
    template = Template(fmt) if fmt else None

    if opts.album:
        objs = list(lib.albums(query=query))
    else:
        objs = list(lib.items(query=query))

    if opts.equal_chance:
        key = attrgetter('albumartist')
        objs.sort(key=key)

        # {artists: objects}
        objs_by_artists = {artist: list(v) for artist, v in groupby(objs, key)}
        artists = objs_by_artists.keys()

        # {artist: count}
        selected_artists = collections.defaultdict(int)
        for _ in range(opts.number):
            selected_artists[random.choice(artists)] += 1

        objs = []
        for artist, count in selected_artists.items():
            objs_from_artist = objs_by_artists[artist]
            number = min(count, len(objs_from_artist))
            objs.extend(random.sample(objs_from_artist, number))

    else:
        number = min(len(objs), opts.number)
        objs = random.sample(objs, number)

    for item in objs:
        print_obj(item, lib, template)

random_cmd = Subcommand('random',
                        help='chose a random track or album')
random_cmd.parser.add_option('-a', '--album', action='store_true',
        help='choose an album instead of track')
random_cmd.parser.add_option('-p', '--path', action='store_true',
        help='print the path of the matched item')
random_cmd.parser.add_option('-f', '--format', action='store',
        help='print with custom format', default=None)
random_cmd.parser.add_option('-n', '--number', action='store', type="int",
        help='number of objects to choose', default=1)
random_cmd.parser.add_option('-e', '--equal-chance', action='store_true',
        help='each artist has the same chance')
random_cmd.func = random_item

class Random(BeetsPlugin):
    def commands(self):
        return [random_cmd]
