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

"""Get a random song or album from the library."""

from __future__ import annotations

import random
from itertools import groupby, islice
from operator import attrgetter
from typing import Iterable, Sequence, TypeVar

from beets.library import Album, Item
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, print_


def random_func(lib, opts, args):
    """Select some random items or albums and print the results."""
    # Fetch all the objects matching the query into a list.
    if opts.album:
        objs = list(lib.albums(args))
    else:
        objs = list(lib.items(args))

    # Print a random subset.
    objs = random_objs(
        objs, opts.album, opts.number, opts.time, opts.equal_chance
    )
    for obj in objs:
        print_(format(obj))


random_cmd = Subcommand("random", help="choose a random track or album")
random_cmd.parser.add_option(
    "-n",
    "--number",
    action="store",
    type="int",
    help="number of objects to choose",
    default=1,
)
random_cmd.parser.add_option(
    "-e",
    "--equal-chance",
    action="store_true",
    help="each artist has the same chance",
)
random_cmd.parser.add_option(
    "-t",
    "--time",
    action="store",
    type="float",
    help="total length in minutes of objects to choose",
)
random_cmd.parser.add_all_common_options()
random_cmd.func = random_func


class Random(BeetsPlugin):
    def commands(self):
        return [random_cmd]


def _length(obj: Item | Album) -> float:
    """Get the duration of an item or album."""
    if isinstance(obj, Album):
        return sum(i.length for i in obj.items())
    else:
        return obj.length


def _equal_chance_permutation(
    objs: Sequence[Item | Album],
    field: str = "albumartist",
    random_gen: random.Random | None = None,
) -> Iterable[Item | Album]:
    """Generate (lazily) a permutation of the objects where every group
    with equal values for `field` have an equal chance of appearing in
    any given position.
    """
    rand = random_gen or random

    # Group the objects by artist so we can sample from them.
    key = attrgetter(field)
    objs = sorted(objs, key=key)
    objs_by_artists = {}
    for artist, v in groupby(objs, key):
        objs_by_artists[artist] = list(v)

    # While we still have artists with music to choose from, pick one
    # randomly and pick a track from that artist.
    while objs_by_artists:
        # Choose an artist and an object for that artist, removing
        # this choice from the pool.
        artist = rand.choice(list(objs_by_artists.keys()))
        objs_from_artist = objs_by_artists[artist]
        i = rand.randint(0, len(objs_from_artist) - 1)
        yield objs_from_artist.pop(i)

        # Remove the artist if we've used up all of its objects.
        if not objs_from_artist:
            del objs_by_artists[artist]


T = TypeVar("T")


def _take(
    iter: Iterable[T],
    num: int,
) -> list[T]:
    """Return a list containing the first `num` values in `iter` (or
    fewer, if the iterable ends early).
    """
    return list(islice(iter, num))


def _take_time(
    iter: Iterable[Item | Album],
    secs: float,
) -> list[Item | Album]:
    """Return a list containing the first values in `iter`, which should
    be Item or Album objects, that add up to the given amount of time in
    seconds.
    """
    out: list[Item | Album] = []
    total_time = 0.0
    for obj in iter:
        length = _length(obj)
        if total_time + length <= secs:
            out.append(obj)
            total_time += length
    return out


def random_objs(
    objs: Sequence[Item | Album],
    number=1,
    time: float | None = None,
    equal_chance: bool = False,
    random_gen: random.Random | None = None,
):
    """Get a random subset of the provided `objs`.

    If `number` is provided, produce that many matches. Otherwise, if
    `time` is provided, instead select a list whose total time is close
    to that number of minutes. If `equal_chance` is true, give each
    artist an equal chance of being included so that artists with more
    songs are not represented disproportionately.
    """
    rand = random_gen or random

    # Permute the objects either in a straightforward way or an
    # artist-balanced way.
    if equal_chance:
        perm = _equal_chance_permutation(objs)
    else:
        perm = list(objs)
        rand.shuffle(perm)

    # Select objects by time our count.
    if time:
        return _take_time(perm, time * 60)
    else:
        return _take(perm, number)
