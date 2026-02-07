# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

from .utils import make_tunelog

if TYPE_CHECKING:
    from collections.abc import Callable

    from beets.logging import Logger

LASTFM = pylast.LastFMNetwork(api_key=plugins.LASTFM_KEY)

PYLAST_EXCEPTIONS = (
    pylast.WSError,
    pylast.MalformedResponseError,
    pylast.NetworkError,
)


class LastFmClient:
    """Client for fetching genres from Last.fm."""

    def __init__(self, log: Logger, min_weight: int):
        """Initialize the client.

        The min_weight parameter filters tags by their minimum weight.
        """
        self._log = log
        self._tunelog = make_tunelog(log)
        self._min_weight = min_weight
        self._genre_cache: dict[str, list[str]] = {}

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

        key = f"{entity}.{'-'.join(str(a) for a in args)}"
        if key not in self._genre_cache:
            args_replaced = [a.replace("\u2010", "-") for a in args]
            self._genre_cache[key] = self.fetch_genre(method(*args_replaced))

        genre = self._genre_cache[key]
        self._tunelog("last.fm (unfiltered) {} tags: {}", entity, genre)
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
