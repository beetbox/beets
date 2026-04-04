# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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


"""Last.fm API client for genre lookups."""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Any, ClassVar

import pylast

from beets import plugins

from .utils import drop_ignored_genres

if TYPE_CHECKING:
    from collections.abc import Callable

    from beets.library import LibModel
    from beets.logging import BeetsLogger

    from .utils import GenreIgnorePatterns

    GenreCache = dict[str, list[str]]
    """Cache mapping entity keys to their genre lists.
    Keys are formatted as 'entity.arg1-arg2-...' (e.g., 'album.artist-title').
    Values are lists of lowercase genre strings."""

LASTFM = pylast.LastFMNetwork(api_key=plugins.LASTFM_KEY)

PYLAST_EXCEPTIONS = (
    pylast.WSError,
    pylast.MalformedResponseError,
    pylast.NetworkError,
)


class LastFmClient:
    """Client for fetching genres from Last.fm."""

    FETCH_METHODS: ClassVar[
        dict[
            str,
            tuple[Callable[..., Any], Callable[[LibModel], tuple[str, ...]]],
        ]
    ] = {
        "track": (LASTFM.get_track, lambda obj: (obj.artist, obj.title)),
        "album": (LASTFM.get_album, lambda obj: (obj.albumartist, obj.album)),
        "artist": (LASTFM.get_artist, lambda obj: (obj.artist,)),
        "album_artist": (LASTFM.get_artist, lambda obj: (obj.albumartist,)),
    }

    def __init__(
        self,
        log: BeetsLogger,
        min_weight: int,
        ignore_patterns: GenreIgnorePatterns,
    ):
        """Initialize the client.

        The min_weight parameter filters tags by their minimum weight.
        The ignorelist filters forbidden genres directly after Last.fm lookup.
        """
        self._log = log
        self._min_weight = min_weight
        self._ignore_patterns: GenreIgnorePatterns = ignore_patterns
        self._genre_cache: GenreCache = {}

    def fetch_genres(
        self, obj: pylast.Album | pylast.Artist | pylast.Track
    ) -> list[str]:
        """Return genres for a pylast entity."""
        try:
            res = obj.get_top_tags()
        except PYLAST_EXCEPTIONS as exc:
            self._log.debug("last.fm error: {}", exc)
            return []
        except Exception as exc:
            # Isolate bugs in pylast.
            self._log.debug("{}", traceback.format_exc())
            self._log.error("error in pylast library: {}", exc)
            return []

        # Filter by weight (optionally).
        if min_weight := self._min_weight:
            res = [el for el in res if (int(el.weight or 0)) >= min_weight]

        # Get strings from tags.
        return [el.item.get_name().lower() for el in res]

    def _last_lookup(
        self, entity: str, method: Callable[..., Any], *args: str
    ) -> list[str]:
        """Get genres based on the named entity using the callable `method`
        whose arguments are given in the sequence `args`. The genre lookup
        is cached based on the entity name and the arguments.

        Before the lookup, each argument has the "-" Unicode character replaced
        with its rough ASCII equivalents in order to return better results from
        the Last.fm database.
        """
        # Shortcut if we're missing metadata.
        if any(not s for s in args):
            return []

        args_replaced = [a.replace("\u2010", "-") for a in args]
        key = f"{entity}.{'-'.join(str(a) for a in args_replaced)}"
        if key not in self._genre_cache:
            self._genre_cache[key] = self.fetch_genres(method(*args_replaced))

        genres = self._genre_cache[key]
        self._log.extra_debug(
            "last.fm (unfiltered) {} tags: {}", entity, genres
        )

        # Filter forbidden genres on every call so ignorelist hits are logged.
        # Artist is always the first element in args (album, artist, track lookups).
        return drop_ignored_genres(
            self._log, self._ignore_patterns, genres, args[0]
        )

    def fetch(self, kind: str, obj: LibModel, *args: str) -> list[str]:
        """Fetch Last.fm genres for the specified kind and entity.

        Use ``args`` if provided, otherwise derive arguments from the object.
        """
        method, arg_fn = self.FETCH_METHODS[kind]
        return self._last_lookup(kind, method, *(args or arg_fn(obj)))
