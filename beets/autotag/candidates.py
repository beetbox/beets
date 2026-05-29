from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any, ClassVar, Generic, overload

from beets import config, logging, metadata_plugins

from .distance import VA_ARTISTS
from .hooks import AlbumInfo, InfoT, TrackInfo
from .match import AlbumMatch, MatchT, TrackMatch

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from beets.autotag import Source

    from .hooks import Info

    JSONDict = dict[str, Any]

# Global logger.
log = logging.getLogger("beets")


class Recommendation(IntEnum):
    """Indicates a qualitative suggestion to the user about what should
    be done with a given match.
    """

    none = 0
    low = 1
    medium = 2
    strong = 3


@dataclass
class Candidates(Generic[InfoT, MatchT], Sequence[MatchT]):
    MATCH_CLASS: ClassVar[type[MatchT]]

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

    def add_info(self, info: InfoT) -> None:
        log.debug("Candidate: {!r}", info)

        if info.identifier in self.candidate_by_id:
            log.debug("Duplicate.")
            return

        if match := self.MATCH_CLASS.try_create(info, self.source):
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

    MATCH_CLASS = AlbumMatch

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

    MATCH_CLASS = TrackMatch

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
