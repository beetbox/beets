# This file is part of beets.
# Copyright 2023, Max Rumpf.
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

"""Plugin to rewrite fields based on a given query."""

import re
import shlex
from collections import defaultdict

import confuse

from beets.dbcore import AndQuery, query_from_strings
from beets.dbcore.types import MULTI_VALUE_DSV
from beets.library import Album, Item
from beets.plugins import BeetsPlugin
from beets.ui import UserError


def simple_rewriter(field, rules):
    """Template field function factory.

    Create a template field function that rewrites the given field
    with the given rewriting rules.
    ``rules`` must be a list of (pattern, replacement) pairs.
    """

    def fieldfunc(item):
        value = item._values_fixed[field]
        for pattern, replacement in rules:
            if pattern.match(value.lower()):
                # Rewrite activated.
                return replacement
        # Not activated; return original value.
        return value

    return fieldfunc


def advanced_rewriter(field, rules):
    """Template field function factory.

    Create a template field function that rewrites the given field
    with the given rewriting rules.
    ``rules`` must be a list of (query, replacement) pairs.
    """

    def fieldfunc(item):
        value = item._values_fixed[field]
        for query, replacement in rules:
            if query.match(item):
                # Rewrite activated.
                return replacement
        # Not activated; return original value.
        return value

    return fieldfunc


class AdvancedRewritePlugin(BeetsPlugin):
    """Plugin to rewrite fields based on a given query."""

    def __init__(self):
        """Parse configuration and register template fields for rewriting."""
        super().__init__()

        template = confuse.Sequence(
            confuse.OneOf(
                [
                    confuse.MappingValues(str),
                    {
                        "match": str,
                        "replacements": confuse.MappingValues(
                            confuse.OneOf([str, confuse.Sequence(str)]),
                        ),
                    },
                ]
            )
        )

        # Gather all the rewrite rules for each field.
        simple_rules = defaultdict(list)
        advanced_rules = defaultdict(list)
        for rule in self.config.get(template):
            if "match" not in rule:
                # Simple syntax
                if len(rule) != 1:
                    raise UserError(
                        "Simple rewrites must have only one rule, "
                        "but found multiple entries. "
                        "Did you forget to prepend a dash (-)?"
                    )
                key, value = next(iter(rule.items()))
                try:
                    fieldname, pattern = key.split(None, 1)
                except ValueError:
                    raise UserError(
                        f"Invalid simple rewrite specification {key}"
                    )
                if fieldname not in Item._fields:
                    raise UserError(
                        f"invalid field name {fieldname} in rewriter"
                    )
                self._log.debug(
                    f"adding simple rewrite '{pattern}' → '{value}' "
                    f"for field {fieldname}"
                )
                pattern = re.compile(pattern.lower())
                simple_rules[fieldname].append((pattern, value))
                if fieldname == "artist":
                    # Special case for the artist field: apply the same
                    # rewrite for "albumartist" as well.
                    simple_rules["albumartist"].append((pattern, value))
            else:
                # Advanced syntax
                match = rule["match"]
                replacements = rule["replacements"]
                if len(replacements) == 0:
                    raise UserError(
                        "Advanced rewrites must have at least one replacement"
                    )
                query = query_from_strings(
                    AndQuery,
                    Item,
                    prefixes={},
                    query_parts=shlex.split(match),
                )
                for fieldname, replacement in replacements.items():
                    if fieldname not in Item._fields:
                        raise UserError(
                            f"Invalid field name {fieldname} in rewriter"
                        )
                    self._log.debug(
                        f"adding advanced rewrite to '{replacement}' "
                        f"for field {fieldname}"
                    )
                    if isinstance(replacement, list):
                        if Item._fields[fieldname] is not MULTI_VALUE_DSV:
                            raise UserError(
                                f"Field {fieldname} is not a multi-valued field "
                                f"but a list was given: {', '.join(replacement)}"
                            )
                    elif isinstance(replacement, str):
                        if Item._fields[fieldname] is MULTI_VALUE_DSV:
                            replacement = list(replacement)
                    else:
                        raise UserError(
                            f"Invalid type of replacement {replacement} "
                            f"for field {fieldname}"
                        )

                    advanced_rules[fieldname].append((query, replacement))
                    # Special case for the artist(s) field:
                    # apply the same rewrite for "albumartist(s)" as well.
                    if fieldname == "artist":
                        advanced_rules["albumartist"].append(
                            (query, replacement)
                        )
                    elif fieldname == "artists":
                        advanced_rules["albumartists"].append(
                            (query, replacement)
                        )
                    elif fieldname == "artist_sort":
                        advanced_rules["albumartist_sort"].append(
                            (query, replacement)
                        )

        # Replace each template field with the new rewriter function.
        for fieldname, fieldrules in simple_rules.items():
            getter = simple_rewriter(fieldname, fieldrules)
            self.template_fields[fieldname] = getter
            if fieldname in Album._fields:
                self.album_template_fields[fieldname] = getter

        for fieldname, fieldrules in advanced_rules.items():
            getter = advanced_rewriter(fieldname, fieldrules)
            self.template_fields[fieldname] = getter
            if fieldname in Album._fields:
                self.album_template_fields[fieldname] = getter
