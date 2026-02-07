# This file is part of beets.
# Copyright 2026, J0J0 Todos.
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


"""Shared utility functions for the lastgenre plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from beets import config

if TYPE_CHECKING:
    from collections.abc import Callable

    from beets.logging import Logger


def make_tunelog(log: Logger) -> Callable[..., None]:
    """Create a tunelog function bound to a specific logger.

    Returns a callable that logs tuning messages at DEBUG level when
    verbosity is high enough.
    """

    def tunelog(msg: str, *args: Any, **kwargs: Any) -> None:
        if config["verbose"].as_number() >= 3:
            log.debug(msg, *args, **kwargs)

    return tunelog
