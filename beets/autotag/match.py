"""Matches existing metadata with canonical information to identify
releases and tracks.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar, overload

import lap
import numpy as np
from typing_extensions import Self

from beets import config, logging, metadata_plugins, plugins
from beets.util import cached_classproperty

from .distance import VA_ARTISTS, distance, track_distance
from .hooks import AlbumInfo, InfoT, TrackInfo

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from beets.autotag import Source
    from beets.library import Album, Item

    from .distance import Distance
    from .hooks import Info

    JSONDict = dict[str, Any]

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


# Primary matching functionality.


def assign_items(
    items: Sequence[Item], tracks: Sequence[TrackInfo]
) -> tuple[list[tuple[Item, TrackInfo]], list[Item], list[TrackInfo]]:
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
    return list(mapping.items()), extra_items, extra_tracks


# Structures that compose all the information for a candidate match.
@dataclass
class Match(Generic[InfoT]):
    """Represent a chosen metadata candidate and its application behavior."""

    disambig_fields_key: ClassVar[str]

    distance: Distance
    info: InfoT

    @classmethod
    def try_create(cls, info: InfoT, source: Source) -> Self | None:
        raise NotImplementedError

    def apply_metadata(self) -> None:
        """Apply this match's metadata to its target library objects."""
        raise NotImplementedError

    @cached_property
    def type(self) -> str:
        return self.info.type.lower()

    @cached_property
    def config_from_scratch(self) -> bool:
        return bool(config["import"]["from_scratch"])

    def from_scratch(self, override: bool | None) -> bool:
        if override is not None:
            return override

        return self.config_from_scratch

    @property
    def disambig_fields(self) -> Sequence[str]:
        """Return configured disambiguation fields that exist on this match."""
        chosen_fields = config["match"][self.disambig_fields_key].as_str_seq()
        valid_fields = [f for f in chosen_fields if f in self.info]
        if missing_fields := set(chosen_fields) - set(valid_fields):
            log.warning(
                "Disambiguation string keys {} do not exist.", missing_fields
            )

        return valid_fields

    @property
    def base_disambig_data(self) -> JSONDict:
        """Return supplemental values used when formatting disambiguation."""
        return {}

    @property
    def disambig_string(self) -> str:
        """Build a display string from the candidate's disambiguation fields.

        Merges base disambiguation data with instance-specific field values,
        then formats them as a comma-separated string in field definition order.
        """
        data = {
            k: self.info[k] for k in self.disambig_fields
        } | self.base_disambig_data
        return ", ".join(str(data[k]) for k in self.disambig_fields)


@dataclass
class AlbumMatch(Match[AlbumInfo]):
    """Represent an album candidate together with its item-to-track mapping."""

    disambig_fields_key = "album_disambig_fields"

    info: AlbumInfo
    mapping: dict[Item, TrackInfo]
    extra_items: list[Item] = field(default_factory=list)
    extra_tracks: list[TrackInfo] = field(default_factory=list)

    @cached_classproperty
    def required_fields(cls) -> Sequence[str]:
        return config["match"]["required"].as_str_seq()

    @cached_classproperty
    def ignored_fields(cls) -> Sequence[str]:
        return config["match"]["ignored"].as_str_seq()

    def __post_init__(self) -> None:
        """Notify listeners when an album candidate has been matched."""
        plugins.send("album_matched", match=self)

    @classmethod
    def try_create(cls, info: AlbumInfo, source: Source) -> Self | None:
        """Validate and create an AlbumMatch from the given info and source."""
        log.debug("Candidate: {!r}", info)

        # Discard albums with zero tracks.
        if not info.tracks:
            log.debug("No tracks.")
            return None

        # Discard matches without required tags.
        if missing_tags := {
            f for f in cls.required_fields if info.get(f) is None
        }:
            log.debug("Ignored. Missing required tag: {}", missing_tags)
            return None

        # Find mapping between the items and the track info.
        item_info_pairs, extra_items, extra_tracks = assign_items(
            source.items, info.tracks
        )

        # Get the change distance.
        _distance = distance(
            source.data, info, item_info_pairs, len(extra_items)
        )

        # Skip matches with ignored penalties.
        penalties = [key for key, _ in _distance]
        for penalty in cls.ignored_fields:
            if penalty in penalties:
                log.debug("Ignored. Penalty: {}", penalty)
                return None

        log.debug("Success. Distance: {}", _distance)
        return cls(
            _distance, info, dict(item_info_pairs), extra_items, extra_tracks
        )

    @property
    def item_info_pairs(self) -> list[tuple[Item, TrackInfo]]:
        """Return matched items together with their selected track metadata."""
        return list(self.mapping.items())

    @property
    def items(self) -> list[Item]:
        """Return the items that participate in this album match."""
        return [i for i, _ in self.item_info_pairs]

    @property
    def base_disambig_data(self) -> JSONDict:
        """Return album-specific values used in disambiguation displays."""
        return {
            "media": (
                f"{mediums}x{self.info.media}"
                if (mediums := self.info.mediums) and mediums > 1
                else self.info.media
            )
        }

    @property
    def merged_pairs(self) -> list[tuple[Item, JSONDict]]:
        """Generate item-data pairs with album-level fallback values."""
        return [
            (i, ti.merge_with_album(self.info))
            for i, ti in self.item_info_pairs
        ]

    def apply_metadata(self, from_scratch: bool | None = None) -> None:
        """Apply metadata to each of the items.

        If ``from_scratch`` is provided, its value determines whether the
        items existing metadata are cleared before applying new metadata.
        Otherwise, the configured ``from_scratch`` setting is used.
        """
        for item, data in self.merged_pairs:
            if self.from_scratch(from_scratch):
                item.clear()

            item.update(data)

    def apply_album_metadata(self, album: Album) -> None:
        """Apply album-level metadata to the Album object."""
        album.update(self.info.item_data)


@dataclass
class TrackMatch(Match[TrackInfo]):
    """Represent a singleton candidate and the item it updates."""

    disambig_fields_key = "singleton_disambig_fields"

    info: TrackInfo
    item: Item

    @classmethod
    def try_create(cls, info: TrackInfo, source: Source) -> Self | None:
        log.debug("Candidate: {!r}", info)

        return cls(
            track_distance(source.items[0], info, incl_artist=True),
            info,
            source.items[0],
        )

    @property
    def base_disambig_data(self) -> JSONDict:
        """Return singleton-specific values used in disambiguation displays."""
        return {
            "index": f"Index {self.info.index}",
            "track_alt": f"Track {self.info.track_alt}",
            "album": (
                f"[{self.info.album}]"
                if (
                    config["import"]["singleton_album_disambig"].get()
                    and self.info.album
                )
                else ""
            ),
        }

    def apply_metadata(self, from_scratch: bool | None = None) -> None:
        """Apply metadata to the item.

        If ``from_scratch`` is provided, its value determines whether the
        item's existing metadata is cleared before applying new metadata.
        Otherwise, the configured ``from_scratch`` setting is used.
        """
        if self.from_scratch(from_scratch):
            self.item.clear()

        self.item.update(self.info.item_data)


MatchT = TypeVar("MatchT", bound=Match[Any])


@dataclass
class Candidates(Sequence[MatchT], Generic[InfoT, MatchT]):
    source: Source
    candidate_by_id: dict[Info.Identifier, MatchT] = field(default_factory=dict)

    def __iter__(self) -> Iterator[MatchT]:
        return iter(self.matches)

    def __len__(self) -> int:
        return len(self.matches)

    @overload
    def __getitem__(self, i: int) -> MatchT: ...

    @overload
    def __getitem__(self, i: slice) -> Sequence[MatchT]: ...

    def __getitem__(self, i: int | slice) -> MatchT | Sequence[MatchT]:
        return self.matches[i]

    @property
    def matches(self) -> list[MatchT]:
        return sorted(self.candidate_by_id.values(), key=lambda m: m.distance)

    @property
    def recommendation(self) -> Recommendation:
        """Given a sorted list of AlbumMatch or TrackMatch objects, return a
        recommendation based on the results' distances.

        If the recommendation is higher than the configured maximum for
        an applied penalty, the recommendation will be downgraded to the
        configured maximum for that penalty.
        """
        matches = self.matches
        if not matches:
            # No candidates: no recommendation.
            return Recommendation.none

        # Basic distance thresholding.
        min_dist = matches[0].distance
        if min_dist < config["match"]["strong_rec_thresh"].as_number():
            # Strong recommendation level.
            rec = Recommendation.strong
        elif min_dist <= config["match"]["medium_rec_thresh"].as_number():
            # Medium recommendation level.
            rec = Recommendation.medium
        elif len(matches) == 1:
            # Only a single candidate.
            rec = Recommendation.low
        elif (
            matches[1].distance - min_dist
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
        if isinstance(matches[0], AlbumMatch):
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

    def create_match(self, info: InfoT) -> MatchT | None:
        raise NotImplementedError

    def add_info(self, info: InfoT) -> None:
        log.debug("Candidate: {!r}", info)

        if info.identifier in self.candidate_by_id:
            log.debug("Duplicate.")
            return

        if match := self.create_match(info):
            self.candidate_by_id[info.identifier] = match

    def add_infos(self, infos: Iterable[InfoT]) -> None:
        for info in infos:
            self.add_info(info)

    def search_ids(self, search_ids: list[str]) -> None:
        log.debug("Searching for {} IDs: {}", self.source.type, search_ids)
        self.add_infos(self.get_id_candidates(search_ids))

        log.debug("Found {} candidates.", len(self))

    def search_library_id(self, id_: str, consensus: bool) -> None:
        """Add candidates for the given ID from the library.

        Make sure that the ID is present and that there is consensus on it among
        the items being tagged.
        """
        if not id_:
            log.debug("No {} ID found.", self.source.type)
        elif not consensus:
            log.debug("No {} ID consensus.", self.source.type)
        else:
            log.debug(
                "Searching for discovered {} ID from the library: {}",
                self.source.type,
                id_,
            )
            self.add_infos(self.get_id_candidates([id_]))

    def get_id_candidates(self, search_ids: Sequence[str]) -> Iterable[InfoT]:
        raise NotImplementedError

    def get_search_candidates(
        self, search_artist: str, search_name: str
    ) -> Iterable[InfoT]:
        raise NotImplementedError

    def search(self, search_artist: str, search_name: str) -> None:
        log.debug(
            "{} Search terms: {} - {}",
            self.source.type.capitalize(),
            search_artist,
            search_name,
        )

        self.add_infos(self.get_search_candidates(search_artist, search_name))

        log.debug("Evaluating {} candidates.", len(self))

    def resolve(self, search_ids: list[str]) -> None:
        log.debug("Tagging {}", self.source.desc)
        if search_ids:
            self.search_ids(search_ids)
        else:
            self.search_library_id(self.source.id, self.source.id_consensus)
            if (
                not config["import"]["timid"]
                and (rec := self.recommendation) == Recommendation.strong
            ):
                log.debug(
                    "{} ID match recommendation is {}",
                    self.source.type.capitalize(),
                    rec,
                )
            else:
                self.search(self.source.artist, self.source.name)


class AlbumCandidates(Candidates[AlbumInfo, AlbumMatch]):
    """Find metadata for an album.

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

    def create_match(self, info: AlbumInfo) -> AlbumMatch | None:
        return AlbumMatch.try_create(info, self.source)

    def get_id_candidates(
        self, search_ids: Sequence[str]
    ) -> Iterable[AlbumInfo]:
        return metadata_plugins.albums_for_ids(search_ids)

    def get_search_candidates(
        self, search_artist: str, search_name: str
    ) -> Iterable[AlbumInfo]:
        if va_likely := (
            self.source.va_likely or search_artist.lower() in VA_ARTISTS
        ):
            log.debug("Album might be VA: {}", va_likely)

        return metadata_plugins.candidates(
            self.source.items, search_artist, search_name, va_likely
        )


class TrackCandidates(Candidates[TrackInfo, TrackMatch]):
    """Find metadata for a single track.

    `search_artist` and `search_title` may be used to override the item
    metadata in the search query. `search_ids` may be used for restricting the
    search to a list of metadata backend IDs.
    """

    def create_match(self, info: TrackInfo) -> TrackMatch | None:
        return TrackMatch.try_create(info, self.source)

    def get_id_candidates(
        self, search_ids: Sequence[str]
    ) -> Iterable[TrackInfo]:
        return metadata_plugins.tracks_for_ids(search_ids)

    def get_search_candidates(
        self, search_artist: str, search_name: str
    ) -> Iterable[TrackInfo]:
        return metadata_plugins.item_candidates(
            self.source.items[0], search_artist, search_name
        )
