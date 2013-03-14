# This file is part of beets.
# Copyright 2013, Philippe Mongeau.
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

"""Provides a fuzzy matching query.
"""

from beets.plugins import BeetsPlugin
from beets.library import PluginQuery
from beets import util
import beets
from beets.util import confit
import difflib


class FuzzyQuery(PluginQuery):
    def __init__(self, field, pattern):
        super(FuzzyQuery, self).__init__(field, pattern)
        try:
            self.threshold = beets.config['fuzzy']['threshold'].as_number()
        except confit.NotFoundError:
            self.threshold = 0.7

    def match(self, pattern, val):
        if pattern is None:
            return False
        val = util.as_string(val)
        # smartcase
        if pattern.islower():
            val = val.lower()
        queryMatcher = difflib.SequenceMatcher(None, pattern, val)
        return queryMatcher.quick_ratio() >= self.threshold


class FuzzyPlugin(BeetsPlugin):
    def __init__(self):
        super(FuzzyPlugin, self).__init__(self)

    def queries(self):
        try:
            prefix = beets.config['fuzzy']['prefix'].get(basestring)
        except confit.NotFoundError:
            prefix = '~'

        return {prefix: FuzzyQuery}
