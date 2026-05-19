from __future__ import annotations

from typing import TYPE_CHECKING

from beets import dbcore, logging

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.library import LibModel

from beets.util.deprecation import deprecate_for_maintainers

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
    deprecate_for_maintainers(
        "'parse_query_parts'", f"beets.library.{model_cls.__name__}.parse_query"
    )
    return model_cls.parse_query(parts)


def parse_query_string(
    s: str, model_cls: type[LibModel]
) -> tuple[dbcore.query.Query, dbcore.sort.Sort]:
    """Given a beets query string, return the `Query` and `Sort` they
    represent.

    The string is split into components using shell-like syntax.
    """
    deprecate_for_maintainers(
        "'parse_query_string'",
        f"beets.library.{model_cls.__name__}.parse_query",
    )
    return model_cls.parse_query(s)
