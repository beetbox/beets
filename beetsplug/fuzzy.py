# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Philippe Mongeau.
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

from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets.dbcore.query import StringFieldQuery
from beets import config
import difflib


class FuzzyQuery(StringFieldQuery):
    @classmethod
    def string_match(cls, pattern, val):
        # smartcase
        if pattern.islower():
            val = val.lower()
        query_matcher = difflib.SequenceMatcher(None, pattern, val)
        threshold = config['fuzzy']['threshold'].as_number()
        return query_matcher.quick_ratio() >= threshold


class FuzzyPlugin(BeetsPlugin):
    def __init__(self):
        super(FuzzyPlugin, self).__init__()
        self.config.add({
            'prefix': '~',
            'threshold': 0.7,
        })

    def queries(self):
        prefix = self.config['prefix'].get(basestring)
        return {prefix: FuzzyQuery}
