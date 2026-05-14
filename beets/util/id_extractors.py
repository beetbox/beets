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

"""Helpers around the extraction of album/track ID's from metadata sources."""

from __future__ import annotations

import re
from enum import Enum, auto
from functools import cache

from typing_extensions import override

from beets import logging

log = logging.getLogger("beets")


class UrlSource(str, Enum):
    @staticmethod
    @override
    def _generate_next_value_(
        name: str, start: int, count: int, last_values: list[str]
    ) -> str:
        return name.lower()

    DISCOGS = auto()
    BANDCAMP = auto()
    SPOTIFY = auto()
    DEEZER = auto()
    TIDAL = auto()
    BEATPORT = auto()
    MUSICBRAINZ = auto()


@cache
def pattern_by_source(source: UrlSource) -> re.Pattern[str]:
    match source:
        case UrlSource.SPOTIFY:
            pattern: str = r"(?:^|open\.spotify\.com/[^/]+/)([0-9A-Za-z]{22})"
        case UrlSource.DEEZER:
            pattern = r"(?:^|deezer\.com/)(?:[a-z]*/)?(?:[^/]+/)?(\d+)"
        case UrlSource.BEATPORT:
            pattern = r"(?:^|beatport\.com/release/.+/)(\d+)$"
        case UrlSource.MUSICBRAINZ:
            pattern = r"(\w{8}(?:-\w{4}){3}-\w{12})"
        case UrlSource.DISCOGS:
            # - plain integer, optionally wrapped in brackets and prefixed by an
            #   'r', as this is how discogs displays the release ID on its webpage.
            # - legacy url format: discogs.com/<name of release>/release/<id>
            # - legacy url short format: discogs.com/release/<id>
            # - current url format: discogs.com/release/<id>-<name of release>
            # See #291, #4080 and #4085 for the discussions leading up to these
            # patterns.
            pattern = r"(?:^|\[?r|discogs\.com/(?:[^/]+/)?release/)(\d+)\b"
        case UrlSource.BANDCAMP:
            # There is no such thing as a Bandcamp album or artist ID, the URL can be
            # used as the identifier. The Bandcamp metadata source plugin works that way
            # - https://github.com/snejus/beetcamp. Bandcamp album URLs usually look
            # like: https://nameofartist.bandcamp.com/album/nameofalbum
            pattern = r"(.+)"
        case UrlSource.TIDAL:
            pattern = r"(?:^|tidal\.com/(?:browse/)?(?:album|track)/)(\d+)"
    return re.compile(pattern)


def extract_release_id(source: str | UrlSource, id_: str) -> str | None:
    """Extract the release ID from a given source and ID.

    Normally, the `id_` is a url string which contains the ID of the
    release. This function extracts the ID from the URL based on the
    `source` provided.
    """
    try:
        source_pattern = pattern_by_source(UrlSource(source.lower()))
    except KeyError:
        log.debug(
            "Unknown source '{}' for ID extraction. Returning id/url as-is.",
            source,
        )
        return id_

    if m := source_pattern.search(str(id_)):
        return m[1]

    return None
