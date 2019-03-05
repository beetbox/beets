# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2019, Vladimir Zhelezov.
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

from __future__ import absolute_import

import inspect
from collections import namedtuple

from six import PY2


def getargspec(func):
    if PY2:
        return inspect.getargspec(func)

    ArgSpec = namedtuple('ArgSpec', 'args varargs keywords defaults')

    sig = inspect.signature(func)
    args = [
        p.name for p in sig.parameters.values()
        if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]
    varargs = [
        p.name for p in sig.parameters.values()
        if p.kind == inspect.Parameter.VAR_POSITIONAL
    ]
    varargs = varargs[0] if varargs else None
    varkw = [
        p.name for p in sig.parameters.values()
        if p.kind == inspect.Parameter.VAR_KEYWORD
    ]
    varkw = varkw[0] if varkw else None
    defaults = tuple(p.default for p in sig.parameters.values()
                     if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
                     and p.default is not p.empty) or None

    return ArgSpec(args, varargs, varkw, defaults)
