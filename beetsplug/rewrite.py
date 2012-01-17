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

from beets.plugins import BeetsPlugin
from beets import ui
from beets import library

log = logging.getLogger('beets')

def rewriter(fieldname, pattern, replacement):
    def fieldfunc(item):
        value = getattr(item, fieldname)
        if pattern.match(value):
            # Rewrite activated.
            return replacement
        else:
            # Not activated; return original value.
            return value
    return fieldfunc

class RewritePlugin(BeetsPlugin):
    template_fields = {}

    def configure(self, config):
        cls = type(self)

        for key, value in config.items('rewrite', True):
            try:
                fieldname, pattern = key.split(None, 1)
            except ValueError:
                raise ui.UserError("invalid rewrite specification")
            if fieldname not in library.ITEM_KEYS:
                raise ui.UserError("invalid field name (%s) in rewriter" %
                                   fieldname)
            log.debug(u'adding template field %s' % key)
            pattern = re.compile(pattern, re.I)

            # Replace the template field with the new function.
            cls.template_fields[fieldname] = rewriter(fieldname, pattern,
                                                      value)
            if fieldname == 'artist':
                # Special case for the artist field: apply the same rewrite for
                # "albumartist" as well.
                cls.template_fields['albumartist'] = rewriter('albumartist',
                                                              pattern, value)
