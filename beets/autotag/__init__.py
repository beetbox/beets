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

"""Facilities for automatically determining files' correct metadata."""

import warnings
from importlib import import_module

from ..util import deprecate_imports
from .hooks import AlbumInfo, AlbumMatch, TrackInfo, TrackMatch
from .match import Proposal, Recommendation, tag_album, tag_item


def __getattr__(name: str):
    if name == "current_metadata":
        warnings.warn(
            (
                f"'beets.autotag.{name}' is deprecated and will be removed in"
                " 3.0.0. Use 'beets.util.get_most_common_tags' instead."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        return import_module("beets.util").get_most_common_tags

    return deprecate_imports(
        __name__, {"Distance": "beets.autotag.distance"}, name, "3.0.0"
    )


__all__ = [
    "AlbumInfo",
    "AlbumMatch",
    "Proposal",
    "Recommendation",
    "TrackInfo",
    "TrackMatch",
    "tag_album",
    "tag_item",
]
