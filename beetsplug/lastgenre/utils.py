"""Lastgenre plugin shared utilities and types."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import re

    from beets.logging import BeetsLogger

    GenreIgnorePatterns = dict[str, list[re.Pattern[str]]]
    """Mapping of artist name to list of compiled case-insensitive patterns."""


def drop_ignored_genres(
    logger: BeetsLogger,
    ignore_patterns: GenreIgnorePatterns,
    genres: list[str],
    artist: str | None = None,
) -> list[str]:
    """Drop genres that match the ignorelist."""
    return [
        g for g in genres if not is_ignored(logger, ignore_patterns, g, artist)
    ]


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
