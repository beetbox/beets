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

PATTERN_BY_SOURCE = {
    "spotify": re.compile(r"(?:^|open\.spotify\.com/[^/]+/)([0-9A-Za-z]{22})"),
    "deezer": re.compile(r"(?:^|deezer\.com/)(?:[a-z]*/)?(?:[^/]+/)?(\d+)"),
    "beatport": re.compile(r"(?:^|beatport\.com/release/.+/)(\d+)$"),
    "musicbrainz": re.compile(r"(\w{8}(?:-\w{4}){3}-\w{12})"),
    # - plain integer, optionally wrapped in brackets and prefixed by an
    #   'r', as this is how discogs displays the release ID on its webpage.
    # - legacy url format: discogs.com/<name of release>/release/<id>
    # - legacy url short format: discogs.com/release/<id>
    # - current url format: discogs.com/release/<id>-<name of release>
    # See #291, #4080 and #4085 for the discussions leading up to these
    # patterns.
    "discogs": re.compile(
        r"(?:^|\[?r|discogs\.com/(?:[^/]+/)?release/)(\d+)\b"
    ),
    # There is no such thing as a Bandcamp album or artist ID, the URL can be
    # used as the identifier. The Bandcamp metadata source plugin works that way
    # - https://github.com/snejus/beetcamp. Bandcamp album URLs usually look
    # like: https://nameofartist.bandcamp.com/album/nameofalbum
    "bandcamp": re.compile(r"(.+)"),
    "tidal": re.compile(r"([^/]+)$"),
}


def extract_release_id(source: str, id_: str) -> str | None:
    if m := PATTERN_BY_SOURCE[source.lower()].search(str(id_)):
        return m[1]
    return None
