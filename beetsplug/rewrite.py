# This file is part of beets.
# Copyright 2012, Adrian Sampson.
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

"""Uses user-specified rewriting rules to canonicalize names for path
formats.
"""
import re
import logging
from collections import defaultdict

from beets.plugins import BeetsPlugin
from beets import ui
from beets import library

log = logging.getLogger('beets')

def rewriter(field, rules):
    """Create a template field function that rewrites the given field
    with the given rewriting rules. ``rules`` must be a list of
    (pattern, replacement) pairs.
    """
    def fieldfunc(item):
        value = getattr(item, field)
        for pattern, replacement in rules:
            if pattern.match(value.lower()):
                # Rewrite activated.
                return replacement
        # Not activated; return original value.
        return value
    return fieldfunc

class RewritePlugin(BeetsPlugin):
    template_fields = {}

    def configure(self, config):
        cls = type(self)

        # Gather all the rewrite rules for each field.
        rules = defaultdict(list)
        if not config.has_section('rewrite'):
            return
        for key, value in config.items('rewrite', True):
            try:
                fieldname, pattern = key.split(None, 1)
            except ValueError:
                raise ui.UserError("invalid rewrite specification")
            if fieldname not in library.ITEM_KEYS:
                raise ui.UserError("invalid field name (%s) in rewriter" %
                                   fieldname)
            log.debug(u'adding template field %s' % key)
            pattern = re.compile(pattern.lower())
            rules[fieldname].append((pattern, value))
            if fieldname == 'artist':
                # Special case for the artist field: apply the same
                # rewrite for "albumartist" as well.
                rules['albumartist'].append((pattern, value))

        # Replace each template field with the new rewriter function.
        for fieldname, fieldrules in rules.iteritems():
            cls.template_fields[fieldname] = rewriter(fieldname, fieldrules)
