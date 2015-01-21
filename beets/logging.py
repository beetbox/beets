# This file is part of beets.
# Copyright 2015, Adrian Sampson.
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

"""A drop-in replacement for the standard-library `logging` module that
allows {}-style log formatting on Python 2 and 3.

Provides everything the "logging" module does. The only difference is
that when getLogger(name) instantiates a logger that logger uses
{}-style formatting.
"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from copy import copy
from logging import *  # noqa
import sys
import subprocess


# We need special hacks for Python 2.6 due to logging.Logger being an
# old- style class and having no loggerClass attribute.
PY26 = sys.version_info[:2] == (2, 6)


def logsafe(val):
    """Coerce a potentially "problematic" value so it can be formatted
    in a Unicode log string.

    This works around a number of pitfalls when logging objects in
    Python 2:
    - Logging path names, which must be byte strings, requires
      conversion for output.
    - Some objects, including some exceptions, will crash when you call
      `unicode(v)` while `str(v)` works fine. CalledProcessError is an
      example.
    """
    # Already Unicode.
    if isinstance(val, unicode):
        return val

    # Bytestring: needs decoding.
    elif isinstance(val, bytes):
        # Blindly convert with UTF-8. Eventually, it would be nice to
        # (a) only do this for paths, if they can be given a distinct
        # type, and (b) warn the developer if they do this for other
        # bytestrings.
        return val.decode('utf8', 'replace')

    # A "problem" object: needs a workaround.
    elif isinstance(val, subprocess.CalledProcessError):
        try:
            return unicode(val)
        except UnicodeDecodeError:
            # An object with a broken __unicode__ formatter. Use __str__
            # instead.
            return str(val).decode('utf8', 'replace')

    # Other objects are used as-is so field access, etc., still works in
    # the format string.
    else:
        return val


class StrFormatLogger(Logger):
    """A version of `Logger` that uses `str.format`-style formatting
    instead of %-style formatting.
    """

    class _LogMessage(object):
        def __init__(self, msg, args, kwargs):
            self.msg = msg
            self.args = args
            self.kwargs = kwargs

        def __str__(self):
            args = [logsafe(a) for a in self.args]
            kwargs = dict((k, logsafe(v)) for (k, v) in self.kwargs.items())
            return self.msg.format(*args, **kwargs)

    def _log(self, level, msg, args, exc_info=None, extra=None, **kwargs):
        """Log msg.format(*args, **kwargs)"""
        m = self._LogMessage(msg, args, kwargs)
        return Logger._log(self, level, m, (), exc_info, extra)
        # We cannot call super(StrFormatLogger, self) because it is not
        # allowed on old-style classes (py2), which Logger is in python 2.6.
        # Moreover, we cannot make StrFormatLogger a new-style class (by
        # declaring 'class StrFormatLogger(Logger, object)' because the class-
        # patching stmt 'logger.__class__ = StrFormatLogger' would not work:
        # both prev & new __class__ values must be either old- or new- style;
        # no mixing allowed.

    if PY26:
        def getChild(self, suffix):
            """Shameless copy from cpython's Lib/logging/__init__.py"""
            if self.root is not self:
                suffix = '.'.join((self.name, suffix))
            return self.manager.getLogger(suffix)

my_manager = copy(Logger.manager)
my_manager.loggerClass = StrFormatLogger


def getLogger(name=None):
    if name:
        return my_manager.getLogger(name)
    else:
        return Logger.root


# On Python 2.6, there is no Manager.loggerClass so we dynamically
# change the logger class. We must be careful to do that on new loggers
# only to avoid side-effects.
if PY26:
    # Wrap Manager.getLogger.
    old_getLogger = my_manager.getLogger

    def new_getLogger(name):
        change_its_type = not isinstance(my_manager.loggerDict.get(name),
                                         Logger)
        # it either does not exist or is a placeholder
        logger = old_getLogger(name)
        if change_its_type:
            logger.__class__ = StrFormatLogger
        return logger

    my_manager.getLogger = new_getLogger


# Offer NullHandler in Python 2.6 to reduce the difference with never versions
if PY26:
    class NullHandler(Handler):
        def handle(self, record):
            pass

        def emit(self, record):
            pass

        def createLock(self):
            self.lock = None
