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
