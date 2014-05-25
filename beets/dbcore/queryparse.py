# This file is part of beets.
# Copyright 2014, Adrian Sampson.
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

"""Parsing of strings into DBCore queries.
"""
import re
import itertools
from . import query


PARSE_QUERY_PART_REGEX = re.compile(
    # Non-capturing optional segment for the keyword.
    r'(?:'
    r'(\S+?)'    # The field key.
    r'(?<!\\):'  # Unescaped :
    r')?'

    r'(.*)',         # The term itself.

    re.I  # Case-insensitive.
)


def parse_query_part(part, query_classes={}, prefixes={},
                     default_class=query.SubstringQuery):
    """Take a query in the form of a key/value pair separated by a
    colon and return a tuple of `(key, value, cls)`. `key` may be None,
    indicating that any field may be matched. `cls` is a subclass of
    `FieldQuery`.

    The optional `query_classes` parameter maps field names to default
    query types; `default_class` is the fallback. `prefixes` is a map
    from query prefix markers and query types. Prefix-indicated queries
    take precedence over type-based queries.

    To determine the query class, two factors are used: prefixes and
    field types. For example, the colon prefix denotes a regular
    expression query and a type map might provide a special kind of
    query for numeric values. If neither a prefix nor a specific query
    class is available, `default_class` is used.

    For instance,
    'stapler' -> (None, 'stapler', SubstringQuery)
    'color:red' -> ('color', 'red', SubstringQuery)
    ':^Quiet' -> (None, '^Quiet', RegexpQuery)
    'color::b..e' -> ('color', 'b..e', RegexpQuery)

    Prefixes may be "escaped" with a backslash to disable the keying
    behavior.
    """
    part = part.strip()
    match = PARSE_QUERY_PART_REGEX.match(part)

    assert match  # Regex should always match.
    key = match.group(1)
    term = match.group(2).replace('\:', ':')

    # Match the search term against the list of prefixes.
    for pre, query_class in prefixes.items():
        if term.startswith(pre):
            return key, term[len(pre):], query_class

    # No matching prefix: use type-based or fallback/default query.
    query_class = query_classes.get(key, default_class)
    return key, term, query_class


def construct_query_part(model_cls, prefixes, query_part):
    """Create a query from a single query component, `query_part`, for
    querying instances of `model_cls`. Return a `Query` instance.
    """
    # Shortcut for empty query parts.
    if not query_part:
        return query.TrueQuery()

    # Get the query classes for each possible field.
    query_classes = {}
    for k, t in itertools.chain(model_cls._fields.items(),
                                model_cls._types.items()):
        query_classes[k] = t.query

    # Parse the string.
    key, pattern, query_class = \
        parse_query_part(query_part, query_classes, prefixes)

    # No key specified.
    if key is None:
        if issubclass(query_class, query.FieldQuery):
            # The query type matches a specific field, but none was
            # specified. So we use a version of the query that matches
            # any field.
            return query.AnyFieldQuery(pattern, model_cls._search_fields,
                                       query_class)
        else:
            # Other query type.
            return query_class(pattern)

    key = key.lower()
    return query_class(key.lower(), pattern, key in model_cls._fields)


def query_from_strings(query_cls, model_cls, prefixes, query_parts):
    """Creates a collection query of type `query_cls` from a list of
    strings in the format used by parse_query_part. `model_cls`
    determines how queries are constructed from strings.
    """
    subqueries = []
    for part in query_parts:
        subqueries.append(construct_query_part(model_cls, prefixes, part))
    if not subqueries:  # No terms in query.
        subqueries = [query.TrueQuery()]
    return query_cls(subqueries)
