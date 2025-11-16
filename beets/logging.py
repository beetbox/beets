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

"""A drop-in replacement for the standard-library `logging` module.

Provides everything the "logging" module does. In addition, beets' logger
(as obtained by `getLogger(name)`) supports thread-local levels, and messages
use {}-style formatting and can interpolate keywords arguments to the logging
calls (`debug`, `info`, etc).
"""

from __future__ import annotations

import threading
from copy import copy
from logging import (
    DEBUG,
    INFO,
    NOTSET,
    WARNING,
    FileHandler,
    Filter,
    Handler,
    Logger,
    NullHandler,
    RootLogger,
    StreamHandler,
)
from typing import TYPE_CHECKING, Any, TypeVar, Union, overload

__all__ = [
    "DEBUG",
    "INFO",
    "NOTSET",
    "WARNING",
    "FileHandler",
    "Filter",
    "Handler",
    "Logger",
    "NullHandler",
    "StreamHandler",
    "getLogger",
]

if TYPE_CHECKING:
    from collections.abc import Mapping

    T = TypeVar("T")
    from types import TracebackType

    # see https://github.com/python/typeshed/blob/main/stdlib/logging/__init__.pyi
    _SysExcInfoType = Union[
        tuple[type[BaseException], BaseException, Union[TracebackType, None]],
        tuple[None, None, None],
    ]
    _ExcInfoType = Union[None, bool, _SysExcInfoType, BaseException]
    _ArgsType = Union[tuple[object, ...], Mapping[str, object]]


def _logsafe(val: T) -> str | T:
    """Coerce `bytes` to `str` to avoid crashes solely due to logging.

    This is particularly relevant for bytestring paths. Much of our code
    explicitly uses `displayable_path` for them, but better be safe and prevent
    any crashes that are solely due to log formatting.
    """
    # Bytestring: Needs decoding to be safe for substitution in format strings.
    if isinstance(val, bytes):
        # Blindly convert with UTF-8. Eventually, it would be nice to
        # (a) only do this for paths, if they can be given a distinct
        # type, and (b) warn the developer if they do this for other
        # bytestrings.
        return val.decode("utf-8", "replace")

    # Other objects are used as-is so field access, etc., still works in
    # the format string. Relies on a working __str__ implementation.
    return val


class StrFormatLogger(Logger):
    """A version of `Logger` that uses `str.format`-style formatting
    instead of %-style formatting and supports keyword arguments.

    We cannot easily get rid of this even in the Python 3 era: This custom
    formatting supports substitution from `kwargs` into the message, which the
    default `logging.Logger._log()` implementation does not.

    Remark by @sampsyo: https://stackoverflow.com/a/24683360 might be a way to
    achieve this with less code.
    """

    class _LogMessage:
        def __init__(
            self,
            msg: str,
            args: _ArgsType,
            kwargs: dict[str, Any],
        ):
            self.msg = msg
            self.args = args
            self.kwargs = kwargs

        def __str__(self):
            args = [_logsafe(a) for a in self.args]
            kwargs = {k: _logsafe(v) for (k, v) in self.kwargs.items()}
            return self.msg.format(*args, **kwargs)

    def _log(
        self,
        level: int,
        msg: object,
        args: _ArgsType,
        exc_info: _ExcInfoType = None,
        extra: Mapping[str, Any] | None = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        **kwargs,
    ):
        """Log msg.format(*args, **kwargs)"""

        if isinstance(msg, str):
            msg = self._LogMessage(msg, args, kwargs)

        return super()._log(
            level,
            msg,
            (),
            exc_info=exc_info,
            extra=extra,
            stack_info=stack_info,
            stacklevel=stacklevel,
        )


class ThreadLocalLevelLogger(Logger):
    """A version of `Logger` whose level is thread-local instead of shared."""

    def __init__(self, name, level=NOTSET):
        self._thread_level = threading.local()
        self.default_level = NOTSET
        super().__init__(name, level)

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


@overload
def getLogger(name: str) -> BeetsLogger: ...
@overload
def getLogger(name: None = ...) -> RootLogger: ...
def getLogger(name=None) -> BeetsLogger | RootLogger:  # noqa: N802
    if name:
        return my_manager.getLogger(name)  # type: ignore[return-value]
    else:
        return Logger.root
