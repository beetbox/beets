"""DBCore is an abstract database package that forms the basis for beets'
Library.
"""

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
    parse_sorted_query,
    query_from_strings,
    sort_from_strings,
)
from .types import Type

__all__ = [
    "AndQuery",
    "Database",
    "FieldQuery",
    "Index",
    "InvalidQueryError",
    "MatchQuery",
    "Model",
    "OrQuery",
    "Query",
    "Results",
    "Type",
    "parse_sorted_query",
    "query_from_strings",
    "sort_from_strings",
]
