from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence


def sanitize_choices(
    choices: Sequence[str], choices_all: Collection[str]
) -> list[str]:
    """Clean up a stringlist configuration attribute: keep only choices
    elements present in choices_all, remove duplicate elements, expand '*'
    wildcard while keeping original stringlist order.
    """
    seen: set[str] = set()
    others = [x for x in choices_all if x not in choices]
    res: list[str] = []
    for s in choices:
        if s not in seen:
            if s in list(choices_all):
                res.append(s)
            elif s == "*":
                res.extend(others)
        seen.add(s)
    return res


def sanitize_pairs(
    pairs: Sequence[tuple[str, str]], pairs_all: Sequence[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Clean up a single-element mapping configuration attribute as returned
    by Confuse's `Pairs` template: keep only two-element tuples present in
    pairs_all, remove duplicate elements, expand ('str', '*') and ('*', '*')
    wildcards while keeping the original order. Note that ('*', '*') and
    ('*', 'whatever') have the same effect.

    For example,

    >>> sanitize_pairs(
    ...     [('foo', 'baz bar'), ('key', '*'), ('*', '*')],
    ...     [('foo', 'bar'), ('foo', 'baz'), ('foo', 'foobar'),
    ...      ('key', 'value')]
    ...     )
    [('foo', 'baz'), ('foo', 'bar'), ('key', 'value'), ('foo', 'foobar')]
    """
    pairs_all = list(pairs_all)
    seen: set[tuple[str, str]] = set()
    others = [x for x in pairs_all if x not in pairs]
    res: list[tuple[str, str]] = []
    for k, values in pairs:
        for v in values.split():
            x = (k, v)
            if x in pairs_all:
                if x not in seen:
                    seen.add(x)
                    res.append(x)
            elif k == "*":
                new = [o for o in others if o not in seen]
                seen.update(new)
                res.extend(new)
            elif v == "*":
                new = [o for o in others if o not in seen and o[0] == k]
                seen.update(new)
                res.extend(new)
    return res
