# This file is part of beets.
# Copyright 2016, Philippe Mongeau.
# Copyright 2025, Sebastian Mohr.
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

from __future__ import annotations

import random
from itertools import groupby, islice
from operator import methodcaller
from typing import TYPE_CHECKING

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, print_

if TYPE_CHECKING:
    import optparse
    from collections.abc import Iterable

    from beets.library import LibModel, Library


def random_func(lib: Library, opts: optparse.Values, args: list[str]):
    """Select some random items or albums and print the results."""
    # Fetch all the objects matching the query into a list.
    objs = lib.albums(args) if opts.album else lib.items(args)

    # Print a random subset.
    for obj in random_objs(
        objs=objs,
        equal_chance_field=opts.field,
        number=opts.number,
        time_minutes=opts.time,
        equal_chance=opts.equal_chance,
    ):
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
    help="each field has the same chance",
)
random_cmd.parser.add_option(
    "-t",
    "--time",
    action="store",
    type="float",
    help="total length in minutes of objects to choose",
)
random_cmd.parser.add_option(
    "--field",
    action="store",
    type="string",
    default="albumartist",
    help="field to use for equal chance sampling (default: albumartist)",
)
random_cmd.parser.add_all_common_options()
random_cmd.func = random_func


class Random(BeetsPlugin):
    def commands(self):
        return [random_cmd]


def _equal_chance_permutation(
    objs: Iterable[LibModel], field: str
) -> Iterable[LibModel]:
    """Generate (lazily) a permutation of the objects where every group
    with equal values for `field` have an equal chance of appearing in
    any given position.
    """
    # Group the objects by field so we can sample from them.
    get_attr = methodcaller("get", field)

    groups = {}
    for k, values in groupby(sorted(objs, key=get_attr), key=get_attr):
        if k is not None:
            vals = list(values)
            # shuffle in category
            random.shuffle(vals)
            groups[str(k)] = vals

    while groups:
        group = random.choice(list(groups.keys()))
        yield groups[group].pop()
        if not groups[group]:
            del groups[group]


def _take_time(
    iter: Iterable[LibModel],
    secs: float,
) -> Iterable[LibModel]:
    """Return a list containing the first values in `iter`, which should
    be Item or Album objects, that add up to the given amount of time in
    seconds.
    """
    total_time = 0.0
    for obj in iter:
        length = obj.length
        if total_time + length <= secs:
            yield obj
            total_time += length


def random_objs(
    objs: Iterable[LibModel],
    equal_chance_field: str,
    number: int = 1,
    time_minutes: float | None = None,
    equal_chance: bool = False,
) -> Iterable[LibModel]:
    """Get a random subset of items, optionally constrained by time or count.

    Args:
    - objs: The sequence of objects to choose from.
    - number: The number of objects to select.
    - time_minutes: If specified, the total length of selected objects
      should not exceed this many minutes.
    - equal_chance: If True, each field has the same chance of being
      selected, regardless of how many tracks they have.
    - random_gen: An optional random generator to use for shuffling.
    """
    # Permute the objects either in a straightforward way or an
    # field-balanced way.
    if equal_chance:
        perm = _equal_chance_permutation(objs, equal_chance_field)
    else:
        perm = list(objs)
        random.shuffle(perm)

    # Select objects by time our count.
    if time_minutes:
        return _take_time(perm, time_minutes * 60)
    else:
        return islice(perm, number)
