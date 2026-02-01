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
    from beets.logging import Logger


def tunelog(log: Logger, msg: str, *args: Any, **kwargs: Any) -> None:
    """Log tuning messages at DEBUG level when verbosity level is high enough."""
    if config["verbose"].as_number() >= 3:
        log.debug(msg, *args, **kwargs)
