from __future__ import annotations

import shlex

import beets
from beets import dbcore, logging, plugins

log = logging.getLogger("beets")


# Special path format key.
PF_KEY_DEFAULT = "default"

# Query construction helpers.


def parse_query_parts(parts, model_cls):
    """Given a beets query string as a list of components, return the
    `Query` and `Sort` they represent.

    Like `dbcore.parse_sorted_query`, with beets query prefixes and
    ensuring that implicit path queries are made explicit with 'path::<query>'
    """
    # Get query types and their prefix characters.
    prefixes = {
        ":": dbcore.query.RegexpQuery,
        "=~": dbcore.query.StringQuery,
        "=": dbcore.query.MatchQuery,
    }
    prefixes.update(plugins.queries())

    # Special-case path-like queries, which are non-field queries
    # containing path separators (/).
    parts = [
        f"path:{s}" if dbcore.query.PathQuery.is_path_query(s) else s
        for s in parts
    ]

    case_insensitive = beets.config["sort_case_insensitive"].get(bool)

    query, sort = dbcore.parse_sorted_query(
        model_cls, parts, prefixes, case_insensitive
    )
    log.debug("Parsed query: {!r}", query)
    log.debug("Parsed sort: {!r}", sort)
    return query, sort


def parse_query_string(s, model_cls):
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
