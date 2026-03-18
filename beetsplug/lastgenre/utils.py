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


"""Lastgenre plugin shared utilities and types."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import re

    from beets.logging import BeetsLogger

    Ignorelist = dict[str, list[re.Pattern[str]]]
    """Mapping of artist name to list of compiled case-insensitive patterns."""


def is_ignored(
    logger: BeetsLogger,
    ignorelist: Ignorelist,
    genre: str,
    artist: str | None = None,
) -> bool:
    """Check if genre tag should be ignored."""
    if not ignorelist:
        return False
    genre_lower = genre.lower()
    for pattern in ignorelist.get("*") or []:
        if pattern.fullmatch(genre_lower):
            logger.extra_debug("ignored (global): {}", genre)
            return True
    for pattern in ignorelist.get((artist or "").lower()) or []:
        if pattern.fullmatch(genre_lower):
            logger.extra_debug("ignored (artist: {}): {}", artist, genre)
            return True
    return False
