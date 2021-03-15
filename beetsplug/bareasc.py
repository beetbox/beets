# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Philippe Mongeau.
# Copyright 2021, Graham R. Cobb.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and ascociated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# This module is adapted from Fuzzy in accordance to the licence of
# that module

"""Provides a bare-ASCII matching query."""

from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets.dbcore.query import StringFieldQuery
from unidecode import unidecode


class BareascQuery(StringFieldQuery):
    """Matches items using bare ASCII, without accents etc."""
    @classmethod
    def string_match(cls, pattern, val):
        # smartcase
        if pattern.islower():
            val = val.lower()
        pattern = unidecode(pattern)
        val = unidecode(val)
        return pattern in val


class BareascPlugin(BeetsPlugin):
    def __init__(self):
        super(BareascPlugin, self).__init__()
        self.config.add({
            'prefix': '#',
        })

    def queries(self):
        prefix = self.config['prefix'].as_str()
        return {prefix: BareascQuery}
