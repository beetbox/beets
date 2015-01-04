"""Allow {}-style formatting on python 2 and 3

Provide everything the "logging" module does, the only difference is that when
getLogger(name) instantiates a logger that logger uses {}-style formatting.
"""

from __future__ import absolute_import
from copy import copy
from logging import *  # noqa


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
        return super(StrFormatLogger, self)._log(level, m, (), exc_info, extra)


my_manager = copy(Logger.manager)
my_manager.loggerClass = StrFormatLogger


def getLogger(name=None):
    if name:
        return my_manager.getLogger(name)
    else:
        return root
