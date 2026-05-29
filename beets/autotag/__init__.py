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

from __future__ import annotations

from importlib import import_module

# Parts of external interface.
from beets.util.deprecation import deprecate_for_maintainers, deprecate_imports

from .distance import Distance, distance, string_dist, track_distance
from .hooks import (
    AlbumInfo,
    AlbumMatch,
    AttrDict,
    Info,
    Match,
    TrackInfo,
    TrackMatch,
    correct_list_fields,
)
from .match import Proposal, Recommendation, assign_items, tag_album, tag_item


def __getattr__(name: str):
    if name == "current_metadata":
        deprecate_for_maintainers(
            f"'beets.autotag.{name}'", "'beets.util.get_most_common_tags'"
        )
        return import_module("beets.util").get_most_common_tags

    return deprecate_imports(__name__, {}, name)


__all__ = [
    "AlbumInfo",
    "AlbumMatch",
    "AttrDict",
    "Distance",
    "Info",
    "Match",
    "Proposal",
    "Recommendation",
    "TrackInfo",
    "TrackMatch",
    "assign_items",
    "correct_list_fields",
    "distance",
    "string_dist",
    "tag_album",
    "tag_item",
    "track_distance",
]
