# This file is part of beets.
# Copyright 2014, Sergei Zimakov.
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

"""Adds support for distance-based sorting. This allows to find
values close to defined point.
"""

from operator import attrgetter

from beets import plugins
from beets.dbcore.query import Sort


class ProximitySort(Sort):
    """Sort by distance from some numeric value
    """
    def __init__(self, model_cls, field, ascending, tail):
        self.model_cls = model_cls
        self.field = field
        self.field_type = model_cls._type(field)
        self.value = self.field_type.parse(tail)

    def order_clause(self):
        if self.is_slow():
            return None
        else:
            return "abs({0}-{1})".format(self.field, self.value)

    def sort(self, objs):
        fieldgetter = attrgetter(self.field)

        def key(o):
            return abs(fieldgetter(o) - self.value)

        return sorted(objs, key=key)

    def is_slow(self):
        """Fast for fixed fields and slow for the rest
        """
        return self.field not in self.model_cls._fields

    def __repr__(self):
        return u'<{0}: {1} near {2}>'.format(
            type(self).__name__,
            self.field,
            self.value
        )


class ProximitySortPlugin(plugins.BeetsPlugin):
    def sorts(self):
        return {'^': ProximitySort}
