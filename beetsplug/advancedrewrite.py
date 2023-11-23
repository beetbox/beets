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

import shlex
from collections import defaultdict

import confuse

from beets import ui
from beets.dbcore import AndQuery, query_from_strings
from beets.library import Album, Item
from beets.plugins import BeetsPlugin


def rewriter(field, rules):
    """Template field function factory.

    Create a template field function that rewrites the given field
    with the given rewriting rules.
    ``rules`` must be a list of (query, replacement) pairs.
    """

    def fieldfunc(item):
        for query, replacement in rules:
            if query.match(item):
                # Rewrite activated.
                return replacement
        # Not activated; return None.
        return None

    return fieldfunc


class AdvancedRewritePlugin(BeetsPlugin):
    """Plugin to rewrite fields based on a given query."""

    def __init__(self):
        """Parse configuration and register template fields for rewriting."""
        super().__init__()

        template = confuse.Sequence(
            {
                "match": str,
                "field": str,
                "replacement": str,
            }
        )

        # Gather all the rewrite rules for each field.
        rules = defaultdict(list)
        for rule in self.config.get(template):
            query = query_from_strings(
                AndQuery,
                Item,
                prefixes={},
                query_parts=shlex.split(rule["match"]),
            )
            fieldname = rule["field"]
            replacement = rule["replacement"]
            if fieldname not in Item._fields:
                raise ui.UserError(
                    "invalid field name (%s) in rewriter" % fieldname
                )
            self._log.debug(
                "adding template field {0} → {1}", fieldname, replacement
            )
            rules[fieldname].append((query, replacement))
            if fieldname == "artist":
                # Special case for the artist field: apply the same
                # rewrite for "albumartist" as well.
                rules["albumartist"].append((query, replacement))

        # Replace each template field with the new rewriter function.
        for fieldname, fieldrules in rules.items():
            getter = rewriter(fieldname, fieldrules)
            self.template_fields[fieldname] = getter
            if fieldname in Album._fields:
                self.album_template_fields[fieldname] = getter
