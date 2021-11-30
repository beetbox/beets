# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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
from collections import defaultdict

from beets.plugins import BeetsPlugin
from beets import ui
from beets import library
from beets import plugins
from beets.library import DefaultTemplateFunctions
from beets.util.functemplate import template


def rewriter(field, rules, og_templ_funcs):
    """Create a template field function that rewrites the given field
    with the given rewriting rules.

    - ``rules`` must be a list of (pattern, replacement) pairs.
    - ``og_plugin_funcs`` must not include any templates from this plugin,
      to avoid infinite loops.
    """
    def fieldfunc(item):
        value = item._values_fixed[field]
        for pattern, replacement in rules:
            if pattern.match(value.lower()):
                # Rewrite activated.
                templ = template(replacement)
                funcs = DefaultTemplateFunctions(item, item._db).functions()
                funcs.update(og_templ_funcs)
                return templ.substitute(item.formatted(for_path=False),
                                        og_templ_funcs)
        # Not activated; return original value.
        return value
    return fieldfunc


def og_getters(prev_templs, new_getters):
    def blankfield(item):
        return ""
    return {k: prev_templs.get(k, blankfield) for k in new_getters.keys()}


class RewritePlugin(BeetsPlugin):
    def __init__(self):
        super().__init__()

        self.config.add({})

        # Gather all the rewrite rules for each field.
        rules = defaultdict(list)
        for key, view in self.config.items():
            value = view.as_str()
            try:
                fieldname, pattern = key.split(None, 1)
            except ValueError:
                raise ui.UserError("invalid rewrite specification")
            if fieldname not in library.Item._fields:
                raise ui.UserError("invalid field name (%s) in rewriter" %
                                   fieldname)
            self._log.debug('adding template field {0}', key)
            pattern = re.compile(pattern.lower())
            rules[fieldname].append((pattern, value))
            if fieldname == 'artist':
                # Special case for the artist field: apply the same
                # rewrite for "albumartist" as well.
                rules['albumartist'].append((pattern, value))

        # Replace each template field with the new rewriter function.
        og_item_getters = og_getters(plugins.item_field_getters(), rules)
        og_album_getters = og_getters(plugins.album_field_getters(), rules)
        for fieldname, fieldrules in rules.items():
            getter = rewriter(fieldname, fieldrules, og_item_getters)
            self.template_fields[fieldname] = getter
            if fieldname in library.Album._fields:
                getter = rewriter(fieldname, fieldrules, og_album_getters)
                self.album_template_fields[fieldname] = getter
