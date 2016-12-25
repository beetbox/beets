# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Philippe Mongeau.
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
from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, decargs, print_
import random
from operator import attrgetter
from itertools import groupby


class Random(BeetsPlugin):

    def commands(self):
        random_cmd = Subcommand(
            'random',
            help=u'chose a random track or album',
        )
        random_cmd.parser.add_option(
            u'-n', u'--number',
            action='store',
            type="int",
            help=u'number of objects to choose',
            default=1,
        )
        random_cmd.parser.add_option(
            u'-e', u'--equal-chance',
            action='store_true',
            help=u'each artist has the same chance',
        )
        random_cmd.parser.add_all_common_options()
        random_cmd.func = self.random_item
        return [random_cmd]

    def random_item(self, lib, opts, args):
        query = decargs(args)

        if opts.album:
            objs = lib.albums(query)
        else:
            objs = lib.items(query)

        if opts.equal_chance:
            objs_list = list(objs)
            self._equal_chance(objs_list, opts)

        number = min(len(objs), opts.number)
        objs = random.sample(objs, number)

        for item in objs:
            print_(format(item))

        return objs

    def _equal_chance(self, objs_list, opts):
        # Group the objects by artist so we can sample from them.
        key = attrgetter('albumartist')
        objs_list.sort(key=key)
        objs_by_artists = {}
        for artist, v in groupby(objs_list, key):
            objs_by_artists[artist] = list(v)

        objs_list = []
        for _ in range(opts.number):
            # Terminate early if we're out of objects to select.
            if not objs_by_artists:
                break

            # Choose an artist and an object for that artist, removing
            # this choice from the pool.
            artist = random.choice(list(objs_by_artists.keys()))
            objs_from_artist = objs_by_artists[artist]
            i = random.randint(0, len(objs_from_artist) - 1)
            objs_list.append(objs_from_artist.pop(i))

            # Remove the artist if we've used up all of its objects.
            if not objs_from_artist:
                del objs_by_artists[artist]
