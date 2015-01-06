"""Allow {}-style logging on python 2 and 3

Provide everything the "logging" module does, the only difference is that when
getLogger(name) instantiates a logger that logger uses {}-style formatting.

It requires special hacks for python 2.6 due to logging.Logger being an old-
style class and having no loggerClass attribute.
"""

from __future__ import absolute_import
from copy import copy
from logging import *  # noqa
import sys


# create a str.format-based logger
class StrFormatLogger(Logger):
    class _LogMessage(object):
        def __init__(self, msg, args, kwargs):
            self.msg = msg
            self.args = args
            self.kwargs = kwargs

        def __str__(self):
            return self.msg.format(*self.args, **self.kwargs)

    def _log(self, level, msg, args, exc_info=None, extra=None, **kwargs):
        """Log msg.format(*args, **kwargs)"""
        m = self._LogMessage(msg, args, kwargs)
        return Logger._log(self, level, m, (), exc_info, extra)
        # we cannot call super(StrFormatLogger, self) because it is not
        # allowed on old-style classes (py2) which Logger is in python 2.6
        # moreover we cannot make StrFormatLogger a new-style class (by
        # declaring 'class StrFormatLogger(Logger, object)' because the class-
        # patching stmt 'logger.__class__ = StrFormatLogger' would not work:
        # both prev & new __class__ values must be either old- or new- style,
        # no mixing allowed.

    if sys.version_info[:2] == (2, 6):
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


if sys.version_info[:2] == (2, 6):
    # no Manager.loggerClass so we dynamically change the logger class
    # we must be careful to do that on new loggers only to avoid side-effects.
    # Wrap Manager.getLogger
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
