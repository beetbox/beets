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
"""Utility resources for the Discogs plugin."""

import http.client
import re
import socket

from discogs_client.exceptions import DiscogsAPIError
from requests.exceptions import ConnectionError

# Exceptions that discogs_client should really handle but does not.
CONNECTION_ERRORS = (
    ConnectionError,
    socket.error,
    http.client.HTTPException,
    ValueError,  # JSON decoding raises a ValueError.
    DiscogsAPIError,
)

DISAMBIGUATION_RE = re.compile(r" \(\d+\)")

TRACK_INDEX_RE = re.compile(
    r"""
    (.*?)   # medium: everything before medium_index.
    (\d*?)  # medium_index: a number at the end of
            # `position`, except if followed by a subtrack index.
            # subtrack_index: can only be matched if medium
            # or medium_index have been matched, and can be
    (
        (?<=\w)\.[\w]+  # a dot followed by a string (A.1, 2.A)
      | (?<=\d)[A-Z]+   # a string that follows a number (1A, B2a)
    )?
    """,
    re.VERBOSE,
)
