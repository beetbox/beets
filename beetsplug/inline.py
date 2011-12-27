# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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

"""Allows inline path template customization code in the config file.
"""
import logging
import traceback

from beets.plugins import BeetsPlugin

log = logging.getLogger('beets')

def compile_expr(expr):
    """Given a Python expression, compile it as a path field function.
    The returned function takes a single argument, an Item, and returns
    a Unicode string. If the expression cannot be compiled, then an
    error is logged and this function returns None.
    """
    try:
        code = compile(u'(%s)' % expr, 'inline', 'eval')
    except SyntaxError:
        log.error(u'syntax error in field expression:\n%s' %
                  traceback.format_exc())
        return None

    def field_func(item):
        return eval(code, dict(item.record))
    return field_func

class InlinePlugin(BeetsPlugin):
    template_fields = {}

    def configure(self, config):
        cls = type(self)

        # Add field expressions.
        for key, value in config.items('pathfields', True):
            log.debug(u'adding template field %s' % key)
            func = compile_expr(value)
            if func is not None:
                cls.template_fields[key] = func
