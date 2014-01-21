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
from beets.dbcore.query import StringFieldQuery
import beets
import difflib


class FuzzyQuery(StringFieldQuery):
    @classmethod
    def string_match(self, pattern, val):
        # smartcase
        if pattern.islower():
            val = val.lower()
        queryMatcher = difflib.SequenceMatcher(None, pattern, val)
        threshold = beets.config['fuzzy']['threshold'].as_number()
        return queryMatcher.quick_ratio() >= threshold


class FuzzyPlugin(BeetsPlugin):
    def __init__(self):
        super(FuzzyPlugin, self).__init__()
        self.config.add({
            'prefix': '~',
            'threshold': 0.7,
        })

    def queries(self):
        prefix = beets.config['fuzzy']['prefix'].get(basestring)
        return {prefix: FuzzyQuery}
