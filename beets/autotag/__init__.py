"""Facilities for automatically determining files' correct metadata."""

from __future__ import annotations

from importlib import import_module

# Parts of external interface.
from beets.util.deprecation import deprecate_for_maintainers, deprecate_imports

from .distance import Distance, distance, string_dist, track_distance
from .hooks import AlbumInfo, Info, TrackInfo, correct_list_fields
from .match import (
    AlbumMatch,
    Match,
    Proposal,
    Recommendation,
    TrackMatch,
    assign_items,
    tag_album,
    tag_item,
)


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
