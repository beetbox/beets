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

    IgnorePatternsByArtist = dict[str, list[re.Pattern[str]]]
    """Mapping of artist key to list of compiled case-insensitive patterns."""

    AliasPatternWithReplacement = tuple[re.Pattern[str], str]
    """A compiled alias regex paired with replacement template string."""


def is_ignored(
    logger: BeetsLogger,
    ignore_patterns: IgnorePatternsByArtist,
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


def normalize_genre(
    logger: BeetsLogger,
    alias_patterns: list[AliasPatternWithReplacement],
    genre: str,
) -> str:
    """Normalize genre using alias replacements.

    Tries each alias entry in order. The first full-match wins; the replacement
    template is expanded via ``re.Match.expand()`` so ``\\g<N>``
    back-references work. Returns original (lowercased) *genre* when no alias
    matches.
    """
    genre_lower = genre.lower()
    for pattern, template in alias_patterns:
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
                logger.extra_debug(
                    "replaced using 'aliases': {} -> {}", genre, expanded
                )
            return expanded
    return genre_lower
