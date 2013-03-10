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

"""Like beet list, but with fuzzy matching
"""

from beets.plugins import BeetsPlugin
from beets.library import PluginQuery
from beets.ui import Subcommand, decargs, print_obj
from beets import config
from beets import util
import difflib

class FuzzyQuery(PluginQuery):
    def __init__(self, field, pattern):
        super(FuzzyQuery, self).__init__(field, pattern)
        # self.field = field
        self.name = 'PLUGIN'
        self.prefix = "~"

    def match(self, pattern, val):
        if pattern is None:
            return False
        val = util.as_string(val)
        queryMatcher = difflib.SequenceMatcher(None, pattern, val)
        return queryMatcher.quick_ratio() > 0.7


class FuzzyPlugin(BeetsPlugin):
    def __init__(self):
        super(FuzzyPlugin, self).__init__(self)

    def queries(self):
        return [FuzzyQuery]
