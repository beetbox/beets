# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

from __future__ import division, absolute_import, print_function

from copy import copy
from logging import *  # noqa
import subprocess
import threading
import six


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
    if isinstance(val, six.text_type):
        return val

    # Bytestring: needs decoding.
    elif isinstance(val, bytes):
        # Blindly convert with UTF-8. Eventually, it would be nice to
        # (a) only do this for paths, if they can be given a distinct
        # type, and (b) warn the developer if they do this for other
        # bytestrings.
        return val.decode('utf-8', 'replace')

    # A "problem" object: needs a workaround.
    elif isinstance(val, subprocess.CalledProcessError):
        try:
            return six.text_type(val)
        except UnicodeDecodeError:
            # An object with a broken __unicode__ formatter. Use __str__
            # instead.
            return str(val).decode('utf-8', 'replace')

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
        return super(StrFormatLogger, self)._log(level, m, (), exc_info, extra)


class ThreadLocalLevelLogger(Logger):
    """A version of `Logger` whose level is thread-local instead of shared.
    """
    def __init__(self, name, level=NOTSET):
        self._thread_level = threading.local()
        self.default_level = NOTSET
        super(ThreadLocalLevelLogger, self).__init__(name, level)

    @property
    def level(self):
        try:
            return self._thread_level.level
        except AttributeError:
            self._thread_level.level = self.default_level
            return self.level

    @level.setter
    def level(self, value):
        self._thread_level.level = value

    def set_global_level(self, level):
        """Set the level on the current thread + the default value for all
        threads.
        """
        self.default_level = level
        self.setLevel(level)


class BeetsLogger(ThreadLocalLevelLogger, StrFormatLogger):
    pass


my_manager = copy(Logger.manager)
my_manager.loggerClass = BeetsLogger


def getLogger(name=None):  # noqa
    if name:
        return my_manager.getLogger(name)
    else:
        return Logger.root
