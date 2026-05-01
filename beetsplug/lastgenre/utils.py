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

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from beets.logging import BeetsLogger

    GenreIgnorePatterns = dict[str, list[re.Pattern[str]]]
    """Mapping of artist name to list of compiled case-insensitive patterns."""

    AliasEntry = tuple[re.Pattern[str], str]
    """A compiled full-match pattern paired with its replacement template."""

    Aliases = list[AliasEntry]
    """Ordered list of (pattern, replacement_template) alias entries."""


def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile *pattern* as a case-insensitive regex.

    Falls back to a literal (``re.escape``'d) pattern when *pattern* is not
    valid regex syntax.
    """
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error:
        return re.compile(re.escape(pattern), re.IGNORECASE)


def is_ignored(
    logger: BeetsLogger,
    ignore_patterns: GenreIgnorePatterns,
    genre: str,
    artist: str | None = None,
) -> bool:
    """Check if genre tag should be ignored."""
    genre_lower = genre.lower()
    for pattern in ignore_patterns.get("*") or []:
        if pattern.fullmatch(genre_lower):
            logger.extra_debug("ignored (global): {}", genre)
            return True
    for pattern in ignore_patterns.get((artist or "").lower()) or []:
        if pattern.fullmatch(genre_lower):
            logger.extra_debug("ignored (artist: {}): {}", artist, genre)
            return True
    return False


def normalize_genre(logger: BeetsLogger, aliases: Aliases, genre: str) -> str:
    """Return the canonical form of *genre* using *aliases*.

    Tries each alias entry in order. The first full-match wins; the replacement
    template is expanded via ``re.Match.expand()`` so ``\\g<N>``
    back-references work. Returns original (lowercased) *genre* when no alias
    matches.
    """
    genre_lower = genre.lower()
    for pattern, template in aliases:
        if m := pattern.fullmatch(genre_lower):
            try:
                expanded = m.expand(template)
            except (re.error, IndexError) as exc:
                logger.warning(
                    "invalid alias template {}; skipping for genre {}: {}",
                    template,
                    genre,
                    exc,
                )
                continue
            if expanded != genre:
                logger.extra_debug("aliased: {} -> {}", genre, expanded)
            return expanded
    return genre_lower
