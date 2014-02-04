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
import dateslib
import datetime,time


class DatesQuery(StringFieldQuery):
    @classmethod
    def value_match(self, pattern, val):
        b, e = dateslib.inputstring(pattern)
        valf = float(val)
        if b <= valf <= e:
            return pattern


class DatesPlugin(BeetsPlugin):
    def __init__(self):
        super(DatesPlugin, self).__init__()
        self.config.add({
            'prefix': '=',

        })

    def queries(self):
        prefix = beets.config['dates']['prefix'].get(basestring)
        return {prefix: DatesQuery}
