"""Get a random song or album from the library."""

from __future__ import annotations

import random
from itertools import groupby, islice
from operator import attrgetter
from typing import TYPE_CHECKING, Any, Iterable, Sequence, Union

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, print_

if TYPE_CHECKING:
    import optparse

    from beets.library import Album, Item, Library

    T = Union[Item, Album]


def random_func(lib: Library, opts: optparse.Values, args: list[str]):
    """Select some random items or albums and print the results."""
    # Fetch all the objects matching the query into a list.
    objs = lib.albums(args) if opts.album else lib.items(args)

    # Print a random subset.
    for obj in random_objs(
        objs=list(objs),
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


NOT_FOUND_SENTINEL = object()


def _equal_chance_permutation(
    objs: Sequence[T],
    field: str = "albumartist",
    random_gen: random.Random | None = None,
) -> Iterable[T]:
    """Generate (lazily) a permutation of the objects where every group
    with equal values for `field` have an equal chance of appearing in
    any given position.
    """
    rand: random.Random = random_gen or random.Random()

    # Group the objects by artist so we can sample from them.
    key = attrgetter(field)

    def get_attr(obj: T) -> Any:
        try:
            return key(obj)
        except AttributeError:
            return NOT_FOUND_SENTINEL

    sorted(objs, key=get_attr)

    groups: dict[str | object, list[T]] = {
        NOT_FOUND_SENTINEL: [],
    }
    for k, values in groupby(objs, key=get_attr):
        groups[k] = list(values)
        # shuffle in category
        rand.shuffle(groups[k])

    # Remove items without the field value.
    del groups[NOT_FOUND_SENTINEL]
    while groups:
        group = rand.choice(list(groups.keys()))
        yield groups[group].pop()
        if not groups[group]:
            del groups[group]


def _take_time(
    iter: Iterable[T],
    secs: float,
) -> Iterable[T]:
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
    objs: Sequence[T],
    number: int = 1,
    time_minutes: float | None = None,
    equal_chance: bool = False,
    random_gen: random.Random | None = None,
) -> Iterable[T]:
    """Get a random subset of items, optionally constrained by time or count.

    Args:
    - objs: The sequence of objects to choose from.
    - number: The number of objects to select.
    - time_minutes: If specified, the total length of selected objects
      should not exceed this many minutes.
    - equal_chance: If True, each artist has the same chance of being
      selected, regardless of how many tracks they have.
    - random_gen: An optional random generator to use for shuffling.
    """
    rand: random.Random = random_gen or random.Random()

    # Permute the objects either in a straightforward way or an
    # artist-balanced way.
    perm: Iterable[T]
    if equal_chance:
        perm = _equal_chance_permutation(objs, random_gen=rand)
    else:
        perm = list(objs)
        rand.shuffle(perm)

    # Select objects by time our count.
    if time_minutes:
        return _take_time(perm, time_minutes * 60)
    else:
        return islice(perm, number)
