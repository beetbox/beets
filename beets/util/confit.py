# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016-2019, Adrian Sampson.
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

from __future__ import division, absolute_import, print_function

import confuse

import warnings
warnings.warn("beets.util.confit is deprecated; use confuse instead")

# Import everything from the confuse module into this module.
for key, value in confuse.__dict__.items():
    if key not in ['__name__']:
        globals()[key] = value


# Beets commit 1a8b20f3541992d4e5c575bfa2b166be5f5868df
def _as_str_seq(self, split=True):
    return self.get(StrSeq(split=split))
ConfigView.as_str_seq = _as_str_seq
del _as_str_seq


# Beets commit 60bffbadbdee3652f65ff495a0436797a5296f71
def _as_pairs(self, default_value=None):
    return self.get(Pairs(default_value=default_value))
ConfigView.as_pairs = _as_pairs
del _as_pairs


# Beets commit 60bffbadbdee3652f65ff495a0436797a5296f71
def _convert_value(self, x, view):
    if isinstance(x, STRING):
        return x
    elif isinstance(x, bytes):
        return x.decode('utf-8', 'ignore')
    else:
        self.fail(u'must be a list of strings', view, True)
StrSeq._convert_value = _convert_value
del _convert_value


# Beets commit 60bffbadbdee3652f65ff495a0436797a5296f71
def _convert(self, value, view):
    if isinstance(value, bytes):
        value = value.decode('utf-8', 'ignore')

    if isinstance(value, STRING):
        if self.split:
            value = value.split()
        else:
            value = [value]
    else:
        try:
            value = list(value)
        except TypeError:
            self.fail(u'must be a whitespace-separated string or a list',
                      view, True)

    return [self._convert_value(v, view) for v in value]
StrSeq.convert = _convert
del _convert


# Beets commits 60bffbadbdee3652f65ff495a0436797a5296f71
#           and 318f0c4d16710712ed49d10c621fbf52705161dd
class Pairs(StrSeq):
    def __init__(self, default_value=None):
        super(Pairs, self).__init__(split=True)
        self.default_value = default_value

    def _convert_value(self, x, view):
        try:
            return (super(Pairs, self)._convert_value(x, view),
                    self.default_value)
        except ConfigTypeError:
            if isinstance(x, collections.Mapping):
                if len(x) != 1:
                    self.fail(u'must be a single-element mapping', view, True)
                k, v = iter_first(x.items())
            elif isinstance(x, collections.Sequence):
                if len(x) != 2:
                    self.fail(u'must be a two-element list', view, True)
                k, v = x
            else:
                self.fail(u'must be a single string, mapping, or a list'
                          u'' + str(x),
                          view, True)
            return (super(Pairs, self)._convert_value(k, view),
                    super(Pairs, self)._convert_value(v, view))


# Cleanup namespace.
del key, value, warnings, confuse
