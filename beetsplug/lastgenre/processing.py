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


"""Genre processing for the lastgenre plugin.

Provides GenreProcessor for validation and transformation of genre names.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .types import Blacklist, Whitelist


class GenreProcessor:
    """Handles genre validation and transformation.

    - Whitelist validation: checking if genres are in the allowed set
    - Blacklist filtering: rejecting forbidden genres (global or artist-specific)
    - Future: normalization/aliasing (e.g., "D&B" -> "Drum And Bass")
    """

    def __init__(
        self,
        whitelist: Whitelist,
        blacklist: Blacklist,
    ):
        self.whitelist = whitelist
        self.blacklist = blacklist

    def is_valid(self, genre: str) -> bool:
        """Check if genre passes whitelist validation."""
        if genre and (not self.whitelist or genre.lower() in self.whitelist):
            return True
        return False

    def is_forbidden(self, genre: str, artist: str | None = None) -> bool:
        """Check if genre matches blacklist patterns.

        Checks global patterns ("*") and artist-specific patterns if artist
        is provided. Case-insensitive matching.
        """
        if not self.blacklist:
            return False

        genre = genre.lower()

        # Check global forbidden patterns
        if "*" in self.blacklist:
            for pattern in self.blacklist["*"]:
                if pattern.search(genre):
                    return True

        # Check artist-specific forbidden patterns
        if artist:
            artist = artist.lower()
            if artist in self.blacklist:
                for pattern in self.blacklist[artist]:
                    if pattern.search(genre):
                        return True

        return False

    def filter_genres(
        self, genres: Iterable[str], artist: str | None = None
    ) -> list[str]:
        """Filter genres through whitelist and blacklist validation.

        Returns genres that:
        - Pass whitelist validation (if configured)
        - Don't match blacklist patterns (if configured)
        - Are not empty or whitespace-only

        Args:
            genres: Iterable of genre strings to filter
            artist: Optional artist name for artist-specific blacklist checks

        Returns:
            List of valid genres that pass all filters
        """
        # First, drop any falsy or whitespace-only genre strings to avoid
        # retaining empty tags from multi-valued fields.
        cleaned = [g for g in genres if g and g.strip()]

        # Short-circuit: if no filters configured, return cleaned list
        if not self.whitelist and not self.blacklist:
            return cleaned

        # Pre-compute blacklist patterns once (avoid repeated dict lookups)
        global_patterns = None
        artist_patterns = None
        artist_lower = None

        if self.blacklist:
            global_patterns = self.blacklist.get("*")
            if artist:
                artist_lower = artist.lower()
                artist_patterns = self.blacklist.get(artist_lower)

        result = []
        for genre in cleaned:
            # Lowercase once per genre
            genre_lower = genre.lower()

            # Whitelist check (if configured)
            if self.whitelist and genre_lower not in self.whitelist:
                continue

            # Blacklist check (if configured) - inline to avoid function call
            forbidden = False
            if global_patterns:
                for pattern in global_patterns:
                    if pattern.search(genre_lower):
                        forbidden = True
                        break

            if not forbidden and artist_patterns:
                for pattern in artist_patterns:
                    if pattern.search(genre_lower):
                        forbidden = True
                        break

            if not forbidden:
                result.append(genre)

        return result

    def _filter_valid(self, genres: Iterable[str]) -> list[str]:
        """Filter genres based on whitelist only.

        .. deprecated::
            Use :meth:`filter_genres` instead for unified validation.

        Returns all genres if no whitelist is configured, otherwise returns
        only genres that are in the whitelist.
        """
        # First, drop any falsy or whitespace-only genre strings to avoid
        # retaining empty tags from multi-valued fields.
        cleaned = [g for g in genres if g and g.strip()]
        if not self.whitelist:
            return cleaned

        return [g for g in cleaned if g.lower() in self.whitelist]
