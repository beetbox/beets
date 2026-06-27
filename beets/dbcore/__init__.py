"""DBCore is an abstract database package that forms the basis for beets'
Library.
"""

from beets.util.deprecation import deprecate_for_maintainers, deprecate_imports

from .db import Database, Index, Model, Results
from .query import (
    AndQuery,
    FieldQuery,
    InvalidQueryError,
    MatchQuery,
    OrQuery,
    Query,
)
from .queryparse import (
    ModelQuery,
    build_and_query,
    parse_sorted_query,
    sort_from_strings,
)
from .types import Type


def __getattr__(name: str):
    if name == "query_from_strings":
        deprecate_for_maintainers(
            f"'beets.dbcore.{name}'", "'beets.dbcore.build_and_query'"
        )
        return build_and_query

    return deprecate_imports(__name__, {}, name)


__all__ = [
    "AndQuery",
    "Database",
    "FieldQuery",
    "Index",
    "InvalidQueryError",
    "MatchQuery",
    "Model",
    "ModelQuery",
    "OrQuery",
    "Query",
    "Results",
    "Type",
    "build_and_query",
    "parse_sorted_query",
    "sort_from_strings",
]
