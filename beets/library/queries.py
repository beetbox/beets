from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from beets import dbcore, logging

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.library import LibModel

log = logging.getLogger("beets")


# Query construction helpers.


def parse_query_parts(
    parts: Sequence[str], model_cls: type[LibModel]
) -> tuple[dbcore.query.Query, dbcore.sort.Sort]:
    """Given a beets query string as a list of components, return the
    `Query` and `Sort` they represent.

    Like `dbcore.parse_sorted_query`, with beets query prefixes and
    ensuring that implicit path queries are made explicit with 'path::<query>'
    """
    query, sort = dbcore.parse_sorted_query(model_cls, parts)
    log.debug("Parsed query: {!r}", query)
    log.debug("Parsed sort: {!r}", sort)
    return query, sort


def parse_query_string(
    s: str, model_cls: type[LibModel]
) -> tuple[dbcore.query.Query, dbcore.sort.Sort]:
    """Given a beets query string, return the `Query` and `Sort` they
    represent.

    The string is split into components using shell-like syntax.
    """
    message = f"Query is not unicode: {s!r}"
    assert isinstance(s, str), message
    try:
        parts = shlex.split(s)
    except ValueError as exc:
        raise dbcore.InvalidQueryError(s, exc)
    return parse_query_parts(parts, model_cls)
