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
from beets import config

log = logging.getLogger('beets')

class InlineError(Exception):
    """Raised when a runtime error occurs in an inline expression.
    """
    def __init__(self, expr, exc):
        super(InlineError, self).__init__(
            (u"error in inline path field expression:\n" \
             u"%s\n%s: %s") % (expr, type(exc).__name__, unicode(exc))
        )

def compile_expr(expr):
    """Given a Python expression, compile it as a path field function.
    The returned function takes a single argument, an Item, and returns
    a Unicode string. If the expression cannot be compiled, then an
    error is logged and this function returns None.
    """
    code = None

    try:
        code = compile(u'(%s)' % expr, 'inline', 'eval')
    except SyntaxError:
        pass

    if code == None:
        try:
            code = compile("""%s""" % expr, 'inline', 'exec')
        except SyntaxError:
            log.error(u'syntax error in field expression:\n%s' %
                      traceback.format_exc())

    if code == None:
        return None

    def field_func(item):
        values = dict(item.record)
        try:
            ret = eval(code, values)
            if ret == None:
                ret = values.get('_', None)
            if ret == None:
                raise Exception('Expression must be a statement or a block of' \
                                ' code storing the result in the "_" variable.')
            return ret
        except Exception as exc:
            raise InlineError(expr, exc)
    return field_func

class InlinePlugin(BeetsPlugin):
    template_fields = {}

    def __init__(self):
        super(InlinePlugin, self).__init__()

        config.add({
            'pathfields': {},
        })

        # Add field expressions.
        for key, view in config['pathfields'].items():
            log.debug(u'adding template field %s' % key)
            func = compile_expr(view.get(unicode))
            if func is not None:
                InlinePlugin.template_fields[key] = func
