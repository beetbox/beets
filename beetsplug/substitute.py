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

"""Uses user-specified substituting rules to canonicalize names for path
formats without modifying the tags of the songs.
"""
from beets.plugins import BeetsPlugin
import re

_substitute_rules = []

class Substitute(BeetsPlugin):
    def __init__(self):
        super(Substitute, self).__init__()
        self.template_funcs['substitute'] = _tmpl_substitute

        for key, view in self.config.items():
            value = view.as_str()
            pattern = re.compile(key.lower())
            _substitute_rules.append((pattern, value))

def _tmpl_substitute(text):
    if text:
         for pattern, replacement in _substitute_rules:
              if pattern.match(text.lower()):
                  return replacement
         return text
    else:
         return u''
