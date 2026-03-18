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
from typing import TYPE_CHECKING, Any

import pylast

from beets import plugins

from .utils import is_ignored

if TYPE_CHECKING:
    from collections.abc import Callable

    from beets.logging import BeetsLogger

    from .utils import Ignorelist

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

    def __init__(
        self, log: BeetsLogger, min_weight: int, ignorelist: Ignorelist
    ):
        """Initialize the client.

        The min_weight parameter filters tags by their minimum weight.
        The ignorelist filters forbidden genres directly after Last.fm lookup.
        """
        self._log = log
        self._min_weight = min_weight
        self._ignorelist: Ignorelist = ignorelist
        self._genre_cache: GenreCache = {}

    def fetch_genre(
        self, lastfm_obj: pylast.Album | pylast.Artist | pylast.Track
    ) -> list[str]:
        """Return genres for a pylast entity. Returns an empty list if
        no suitable genres are found.
        """
        return self._tags_for(lastfm_obj, self._min_weight)

    def _tags_for(
        self,
        obj: pylast.Album | pylast.Artist | pylast.Track,
        min_weight: int | None = None,
    ) -> list[str]:
        """Core genre identification routine.

        Given a pylast entity (album or track), return a list of
        tag names for that entity. Return an empty list if the entity is
        not found or another error occurs.

        If `min_weight` is specified, tags are filtered by weight.
        """
        # Work around an inconsistency in pylast where
        # Album.get_top_tags() does not return TopItem instances.
        # https://github.com/pylast/pylast/issues/86
        obj_to_query: Any = obj
        if isinstance(obj, pylast.Album):
            obj_to_query = super(pylast.Album, obj)

        try:
            res: Any = obj_to_query.get_top_tags()
        except PYLAST_EXCEPTIONS as exc:
            self._log.debug("last.fm error: {}", exc)
            return []
        except Exception as exc:
            # Isolate bugs in pylast.
            self._log.debug("{}", traceback.format_exc())
            self._log.error("error in pylast library: {}", exc)
            return []

        # Filter by weight (optionally).
        if min_weight:
            res = [el for el in res if (int(el.weight or 0)) >= min_weight]

        # Get strings from tags.
        tags: list[str] = [el.item.get_name().lower() for el in res]

        return tags

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
        if key in self._genre_cache:
            raw_genre = self._genre_cache[key]
        else:
            raw_genre = self.fetch_genre(method(*args_replaced))
            # Cache raw results only — filtering always runs so ignorelist
            # hits are always visible in extra_debug logs.
            self._genre_cache[key] = raw_genre

        self._log.extra_debug(
            "last.fm (unfiltered) {} tags: {}", entity, raw_genre
        )

        genre = raw_genre

        # Filter forbidden genres on every call so ignorelist hits are logged.
        if genre and len(args) >= 1:
            # For all current lastfm API calls, the first argument is always the artist:
            # - get_album(artist, album)
            # - get_artist(artist)
            # - get_track(artist, title)
            artist = args[0]
            genre = [
                g
                for g in genre
                if not is_ignored(self._log, self._ignorelist, g, artist)
            ]

        return genre

    def fetch_album_genre(self, albumartist: str, albumtitle: str) -> list[str]:
        """Return genres from Last.fm for the album by albumartist."""
        return self._last_lookup(
            "album", LASTFM.get_album, albumartist, albumtitle
        )

    def fetch_artist_genre(self, artist: str) -> list[str]:
        """Return genres from Last.fm for the artist."""
        return self._last_lookup("artist", LASTFM.get_artist, artist)

    def fetch_track_genre(self, trackartist: str, tracktitle: str) -> list[str]:
        """Return genres from Last.fm for the track by artist."""
        return self._last_lookup(
            "track", LASTFM.get_track, trackartist, tracktitle
        )
