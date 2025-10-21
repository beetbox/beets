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

"""Matches existing metadata with canonical information to identify
releases and tracks.
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Any, NamedTuple, TypeVar

import lap
import numpy as np

from beets import config, logging, metadata_plugins, plugins
from beets.autotag import AlbumInfo, AlbumMatch, TrackInfo, TrackMatch, hooks
from beets.util import get_most_common_tags

from .distance import VA_ARTISTS, distance, track_distance

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from beets.library import Item

# Global logger.
log = logging.getLogger("beets")


# Recommendation enumeration.


class Recommendation(IntEnum):
    """Indicates a qualitative suggestion to the user about what should
    be done with a given match.
    """

    none = 0
    low = 1
    medium = 2
    strong = 3


# A structure for holding a set of possible matches to choose between. This
# consists of a list of possible candidates (i.e., AlbumInfo or TrackInfo
# objects) and a recommendation value.


class Proposal(NamedTuple):
    candidates: Sequence[AlbumMatch | TrackMatch]
    recommendation: Recommendation


# Primary matching functionality.


def assign_items(
    items: Sequence[Item],
    tracks: Sequence[TrackInfo],
) -> tuple[dict[Item, TrackInfo], list[Item], list[TrackInfo]]:
    """Given a list of Items and a list of TrackInfo objects, find the
    best mapping between them. Returns a mapping from Items to TrackInfo
    objects, a set of extra Items, and a set of extra TrackInfo
    objects. These "extra" objects occur when there is an unequal number
    of objects of the two types.
    """
    log.debug("Computing track assignment...")
    # Construct the cost matrix.
    costs = [[float(track_distance(i, t)) for t in tracks] for i in items]
    # Assign items to tracks
    _, _, assigned_item_idxs = lap.lapjv(np.array(costs), extend_cost=True)
    log.debug("...done.")

    # Each item in `assigned_item_idxs` list corresponds to a track in the
    # `tracks` list. Each value is either an index into the assigned item in
    # `items` list, or -1 if that track has no match.
    mapping = {
        items[iidx]: t
        for iidx, t in zip(assigned_item_idxs, tracks)
        if iidx != -1
    }
    extra_items = list(set(items) - mapping.keys())
    extra_items.sort(key=lambda i: (i.disc, i.track, i.title))
    extra_tracks = list(set(tracks) - set(mapping.values()))
    extra_tracks.sort(key=lambda t: (t.index, t.title))
    return mapping, extra_items, extra_tracks


def match_by_id(items: Iterable[Item]) -> AlbumInfo | None:
    """If the items are tagged with an external source ID, return an
    AlbumInfo object for the corresponding album. Otherwise, returns
    None.
    """
    albumids = (item.mb_albumid for item in items if item.mb_albumid)

    # Did any of the items have an MB album ID?
    try:
        first = next(albumids)
    except StopIteration:
        log.debug("No album ID found.")
        return None

    # Is there a consensus on the MB album ID?
    for other in albumids:
        if other != first:
            log.debug("No album ID consensus.")
            return None
    # If all album IDs are equal, look up the album.
    log.debug("Searching for discovered album ID: {}", first)
    return metadata_plugins.album_for_id(first)


def _recommendation(
    results: Sequence[AlbumMatch | TrackMatch],
) -> Recommendation:
    """Given a sorted list of AlbumMatch or TrackMatch objects, return a
    recommendation based on the results' distances.

    If the recommendation is higher than the configured maximum for
    an applied penalty, the recommendation will be downgraded to the
    configured maximum for that penalty.
    """
    if not results:
        # No candidates: no recommendation.
        return Recommendation.none

    # Basic distance thresholding.
    min_dist = results[0].distance
    if min_dist < config["match"]["strong_rec_thresh"].as_number():
        # Strong recommendation level.
        rec = Recommendation.strong
    elif min_dist <= config["match"]["medium_rec_thresh"].as_number():
        # Medium recommendation level.
        rec = Recommendation.medium
    elif len(results) == 1:
        # Only a single candidate.
        rec = Recommendation.low
    elif (
        results[1].distance - min_dist
        >= config["match"]["rec_gap_thresh"].as_number()
    ):
        # Gap between first two candidates is large.
        rec = Recommendation.low
    else:
        # No conclusion. Return immediately. Can't be downgraded any further.
        return Recommendation.none

    # Downgrade to the max rec if it is lower than the current rec for an
    # applied penalty.
    keys = set(min_dist.keys())
    if isinstance(results[0], hooks.AlbumMatch):
        for track_dist in min_dist.tracks.values():
            keys.update(list(track_dist.keys()))
    max_rec_view = config["match"]["max_rec"]
    for key in keys:
        if key in list(max_rec_view.keys()):
            max_rec = max_rec_view[key].as_choice(
                {
                    "strong": Recommendation.strong,
                    "medium": Recommendation.medium,
                    "low": Recommendation.low,
                    "none": Recommendation.none,
                }
            )
            rec = min(rec, max_rec)

    return rec


AnyMatch = TypeVar("AnyMatch", TrackMatch, AlbumMatch)


def _sort_candidates(candidates: Iterable[AnyMatch]) -> Sequence[AnyMatch]:
    """Sort candidates by distance."""
    return sorted(candidates, key=lambda match: match.distance)


def _add_candidate(
    items: Sequence[Item],
    results: dict[Any, AlbumMatch],
    info: AlbumInfo,
):
    """Given a candidate AlbumInfo object, attempt to add the candidate
    to the output dictionary of AlbumMatch objects. This involves
    checking the track count, ordering the items, checking for
    duplicates, and calculating the distance.
    """
    log.debug("Candidate: {0.artist} - {0.album} ({0.album_id})", info)

    # Discard albums with zero tracks.
    if not info.tracks:
        log.debug("No tracks.")
        return

    # Prevent duplicates.
    if info.album_id and info.album_id in results:
        log.debug("Duplicate.")
        return

    # Discard matches without required tags.
    required_tags: Sequence[str] = config["match"]["required"].as_str_seq()
    for req_tag in required_tags:
        if getattr(info, req_tag) is None:
            log.debug("Ignored. Missing required tag: {}", req_tag)
            return

    # Find mapping between the items and the track info.
    mapping, extra_items, extra_tracks = assign_items(items, info.tracks)

    # Get the change distance.
    dist = distance(items, info, mapping)

    # Skip matches with ignored penalties.
    penalties = [key for key, _ in dist]
    ignored_tags: Sequence[str] = config["match"]["ignored"].as_str_seq()
    for penalty in ignored_tags:
        if penalty in penalties:
            log.debug("Ignored. Penalty: {}", penalty)
            return

    log.debug("Success. Distance: {}", dist)
    results[info.album_id] = hooks.AlbumMatch(
        dist, info, mapping, extra_items, extra_tracks
    )


def _parse_search_terms_with_fallbacks(
    *pairs: tuple[str | None, str],
) -> tuple[str, ...]:
    """Given pairs of (search term, fallback), return a tuple of
    search terms. If **all** search terms are empty, returns the fallback. Otherwise,
    return the search terms even if some are empty.

    Examples:
    (("", "F1"), ("B", "F2")) -> ("", "B")
    (("", "F1"), ("", "F2")) -> ("F1", "F2")
    (("A", "F1"), (None, "F2")) -> ("A", "")
    ((None, "F1"), (None, "F2")) -> ("F1", "F2")
    """
    if any(term for term, _ in pairs):
        return tuple(term or "" for term, _ in pairs)
    else:
        return tuple(fallback for _, fallback in pairs)


def tag_album(
    items,
    search_artist: str | None = None,
    search_album: str | None = None,
    search_ids: list[str] | None = None,
) -> tuple[str, str, Proposal]:
    """Return a tuple of the current artist name, the current album
    name, and a `Proposal` containing `AlbumMatch` candidates.

    The artist and album are the most common values of these fields
    among `items`.

    The `AlbumMatch` objects are generated by searching the metadata
    backends. By default, the metadata of the items is used for the
    search. This can be customized by setting the parameters.
    `search_ids` is a list of metadata backend IDs: if specified,
    it will restrict the candidates to those IDs, ignoring
    `search_artist` and `search album`. The `mapping` field of the
    album has the matched `items` as keys.

    The recommendation is calculated from the match quality of the
    candidates.
    """
    # Get current metadata.
    likelies, consensus = get_most_common_tags(items)
    cur_artist: str = likelies["artist"]
    cur_album: str = likelies["album"]
    log.debug("Tagging {} - {}", cur_artist, cur_album)

    # The output result, keys are the MB album ID.
    candidates: dict[Any, AlbumMatch] = {}

    # Search by explicit ID.
    if search_ids:
        for search_id in search_ids:
            log.debug("Searching for album ID: {}", search_id)
            if info := metadata_plugins.album_for_id(search_id):
                _add_candidate(items, candidates, info)
                if opt_candidate := candidates.get(info.album_id):
                    plugins.send("album_matched", match=opt_candidate)

    # Use existing metadata or text search.
    else:
        # Try search based on current ID.
        if info := match_by_id(items):
            _add_candidate(items, candidates, info)
            for candidate in candidates.values():
                plugins.send("album_matched", match=candidate)

            rec = _recommendation(list(candidates.values()))
            log.debug("Album ID match recommendation is {}", rec)
            if candidates and not config["import"]["timid"]:
                # If we have a very good MBID match, return immediately.
                # Otherwise, this match will compete against metadata-based
                # matches.
                if rec == Recommendation.strong:
                    log.debug("ID match.")
                    return (
                        cur_artist,
                        cur_album,
                        Proposal(list(candidates.values()), rec),
                    )

        # Manually provided search terms or fallbacks.
        _search_artist, _search_album = _parse_search_terms_with_fallbacks(
            (search_artist, cur_artist),
            (search_album, cur_album),
        )
        log.debug("Search terms: {} - {}", _search_artist, _search_album)

        # Is this album likely to be a "various artist" release?
        va_likely = (
            (not consensus["artist"])
            or (_search_artist.lower() in VA_ARTISTS)
            or any(item.comp for item in items)
        )
        log.debug("Album might be VA: {}", va_likely)

        # Get the results from the data sources.
        for matched_candidate in metadata_plugins.candidates(
            items, _search_artist, _search_album, va_likely
        ):
            _add_candidate(items, candidates, matched_candidate)
            if opt_candidate := candidates.get(matched_candidate.album_id):
                plugins.send("album_matched", match=opt_candidate)

    log.debug("Evaluating {} candidates.", len(candidates))
    # Sort and get the recommendation.
    candidates_sorted = _sort_candidates(candidates.values())
    rec = _recommendation(candidates_sorted)
    return cur_artist, cur_album, Proposal(candidates_sorted, rec)


def tag_item(
    item: Item,
    search_artist: str | None = None,
    search_title: str | None = None,
    search_ids: list[str] | None = None,
) -> Proposal:
    """Find metadata for a single track. Return a `Proposal` consisting
    of `TrackMatch` objects.

    `search_artist` and `search_title` may be used to override the item
    metadata in the search query. `search_ids` may be used for restricting the
    search to a list of metadata backend IDs.
    """
    # Holds candidates found so far: keys are MBIDs; values are
    # (distance, TrackInfo) pairs.
    candidates = {}
    rec: Recommendation | None = None

    # First, try matching by the external source ID.
    trackids = search_ids or [t for t in [item.mb_trackid] if t]
    if trackids:
        for trackid in trackids:
            log.debug("Searching for track ID: {}", trackid)
            if info := metadata_plugins.track_for_id(trackid):
                dist = track_distance(item, info, incl_artist=True)
                candidates[info.track_id] = hooks.TrackMatch(dist, info)
                # If this is a good match, then don't keep searching.
                rec = _recommendation(_sort_candidates(candidates.values()))
                if (
                    rec == Recommendation.strong
                    and not config["import"]["timid"]
                ):
                    log.debug("Track ID match.")
                    return Proposal(_sort_candidates(candidates.values()), rec)

    # If we're searching by ID, don't proceed.
    if search_ids:
        if candidates:
            assert rec is not None
            return Proposal(_sort_candidates(candidates.values()), rec)
        else:
            return Proposal([], Recommendation.none)

    # Manually provided search terms or fallbacks.
    _search_artist, _search_title = _parse_search_terms_with_fallbacks(
        (search_artist, item.artist),
        (search_title, item.title),
    )
    log.debug("Item search terms: {} - {}", _search_artist, _search_title)

    # Get and evaluate candidate metadata.
    for track_info in metadata_plugins.item_candidates(
        item,
        _search_artist,
        _search_title,
    ):
        dist = track_distance(item, track_info, incl_artist=True)
        candidates[track_info.track_id] = hooks.TrackMatch(dist, track_info)

    # Sort by distance and return with recommendation.
    log.debug("Found {} candidates.", len(candidates))
    candidates_sorted = _sort_candidates(candidates.values())
    rec = _recommendation(candidates_sorted)
    return Proposal(candidates_sorted, rec)
