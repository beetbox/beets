"""Helpers for communicating with the MusicBrainz webservice.

Provides rate-limited HTTP session and convenience methods to fetch and
normalize API responses.

This module centralizes request handling and response shaping so callers can
work with consistently structured data without embedding HTTP or rate-limit
logic throughout the codebase.
"""

from __future__ import annotations

import operator
import re
from dataclasses import dataclass, field
from functools import cached_property, singledispatchmethod, wraps
from itertools import groupby, starmap
from typing import TYPE_CHECKING, Any, Literal, ParamSpec, TypedDict, TypeVar

from requests_ratelimiter import LimiterMixin
from typing_extensions import NotRequired, Unpack

from beets import config, logging

from .requests import RequestHandler, TimeoutAndRetrySession

if TYPE_CHECKING:
    from collections.abc import Callable

    from requests import Response

    from .._typing import JSONDict

log = logging.getLogger("beets")


LUCENE_SPECIAL_CHAR_PAT = re.compile(r'([-+&|!(){}[\]^"~*?:\\/])')

RELEASE_INCLUDES = [
    "artists",
    "media",
    "recordings",
    "release-groups",
    "labels",
    "artist-credits",
    "aliases",
    "recording-level-rels",
    "work-rels",
    "work-level-rels",
    "artist-rels",
    "isrcs",
    "url-rels",
    "release-rels",
    "genres",
    "tags",
]

RECORDING_INCLUDES = [
    "artists",
    "aliases",
    "isrcs",
    "work-level-rels",
    "artist-rels",
]


class LimiterTimeoutSession(LimiterMixin, TimeoutAndRetrySession):
    """HTTP session that enforces rate limits."""


Entity = Literal[
    "area",
    "artist",
    "collection",
    "event",
    "genre",
    "instrument",
    "label",
    "place",
    "recording",
    "release",
    "release-group",
    "series",
    "work",
    "url",
]


class LookupKwargs(TypedDict, total=False):
    includes: NotRequired[list[str]]


class PagingKwargs(TypedDict, total=False):
    limit: NotRequired[int]
    offset: NotRequired[int]


class SearchKwargs(PagingKwargs):
    query: NotRequired[str]


class BrowseKwargs(LookupKwargs, PagingKwargs, total=False):
    pass


class BrowseReleaseGroupsKwargs(BrowseKwargs, total=False):
    artist: NotRequired[str]
    collection: NotRequired[str]
    release: NotRequired[str]


class BrowseRecordingsKwargs(BrowseReleaseGroupsKwargs, total=False):
    work: NotRequired[str]


P = ParamSpec("P")
R = TypeVar("R")


class _Period(TypedDict):
    begin: str | None
    end: str | None
    ended: bool


class Alias(_Period):
    locale: str | None
    name: str
    primary: bool | None
    sort_name: str
    type: (
        Literal[
            "Artist name",
            "Label name",
            "Legal name",
            "Recording name",
            "Release name",
            "Release group name",
            "Search hint",
        ]
        | None
    )
    type_id: str | None


class Artist(TypedDict):
    country: str | None
    disambiguation: str
    id: str
    name: str
    sort_name: str
    type: (
        Literal["Character", "Choir", "Group", "Orchestra", "Other", "Person"]
        | None
    )
    type_id: str | None
    aliases: NotRequired[list[Alias]]
    genres: NotRequired[list[Genre]]
    tags: NotRequired[list[Tag]]


class ArtistCredit(TypedDict):
    artist: Artist
    joinphrase: str
    name: str


class Genre(TypedDict):
    count: int
    disambiguation: str
    id: str
    name: str


class Tag(TypedDict):
    count: int
    name: str


ReleaseStatus = Literal[
    "Bootleg",
    "Cancelled",
    "Expunged",
    "Official",
    "Promotion",
    "Pseudo-Release",
    "Withdrawn",
]

ReleasePackaging = Literal[
    "Book",
    "Box",
    "Cardboard/Paper Sleeve",
    "Cassette Case",
    "Clamshell Case",
    "Digibook",
    "Digifile",
    "Digipak",
    "Discbox Slider",
    "Fatbox",
    "Gatefold Cover",
    "Jewel Case",
    "None",
    "Keep Case",
    "Longbox",
    "Metal Tin",
    "Other",
    "Plastic Sleeve",
    "Slidepack",
    "Slipcase",
    "Snap Case",
    "SnapPack",
    "Slim Jewel Case",
    "Super Jewel Box",
]


ReleaseQuality = Literal["high", "low", "normal"]


class ReleaseGroup(TypedDict):
    aliases: list[Alias]
    artist_credit: list[ArtistCredit]
    disambiguation: str
    first_release_date: str
    genres: list[Genre]
    id: str
    primary_type: Literal["Album", "Broadcast", "EP", "Other", "Single"] | None
    primary_type_id: str | None
    secondary_type_ids: list[str]
    secondary_types: list[
        Literal[
            "Audiobook",
            "Audio drama",
            "Compilation",
            "DJ-mix",
            "Demo",
            "Field recording",
            "Interview",
            "Live",
            "Mixtape/Street",
            "Remix",
            "Soundtrack",
            "Spokenword",
        ]
    ]
    tags: list[Tag]
    title: str


class CoverArtArchive(TypedDict):
    artwork: bool
    back: bool
    count: int
    darkened: bool
    front: bool


class TextRepresentation(TypedDict):
    language: str | None
    script: str | None


class Area(TypedDict):
    disambiguation: str
    id: str
    iso_3166_1_codes: list[str]
    iso_3166_2_codes: NotRequired[list[str]]
    name: str
    sort_name: str
    type: None
    type_id: None


class ReleaseEvent(TypedDict):
    area: Area | None
    date: str


class Label(TypedDict):
    aliases: list[Alias]
    disambiguation: str
    genres: list[Genre]
    id: str
    label_code: int | None
    name: str
    sort_name: str
    tags: list[Tag]
    type: (
        Literal[
            "Bootleg Production",
            "Broadcaster",
            "Distributor",
            "Holding",
            "Imprint",
            "Manufacturer",
            "Original Production",
            "Publisher",
            "Reissue Production",
            "Rights Society",
        ]
        | None
    )
    type_id: str | None


class LabelInfo(TypedDict):
    catalog_number: str | None
    label: Label


class Url(TypedDict):
    id: str
    resource: str


class RelationBase(_Period):
    attribute_ids: dict[str, str]
    attribute_values: dict[str, str]
    attributes: list[str]
    direction: Literal["backward", "forward"]
    source_credit: str
    target_credit: str
    type_id: str


ArtistRelationType = Literal[
    "arranger",
    "art direction",
    "artwork",
    "composer",
    "conductor",
    "copyright",
    "design",
    "design/illustration",
    "editor",
    "engineer",
    "graphic design",
    "illustration",
    "instrument",
    "instrument arranger",
    "liner notes",
    "lyricist",
    "mastering",
    "misc",
    "mix",
    "mix-DJ",
    "performer",
    "phonographic copyright",
    "photography",
    "previous attribution",
    "producer",
    "programming",
    "recording",
    "remixer",
    "sound",
    "vocal",
    "vocal arranger",
    "writer",
]


class ArtistRelation(RelationBase):
    type: ArtistRelationType
    artist: Artist
    attribute_credits: NotRequired[dict[str, str]]


class UrlRelation(RelationBase):
    type: Literal[
        "IMDB samples",
        "IMDb",
        "allmusic",
        "amazon asin",
        "discography entry",
        "discogs",
        "download for free",
        "fanpage",
        "free streaming",
        "lyrics",
        "other databases",
        "purchase for download",
        "purchase for mail-order",
        "secondhandsongs",
        "show notes",
        "songfacts",
        "streaming",
        "wikidata",
        "wikipedia",
    ]
    url: Url


class WorkRelation(RelationBase):
    type: Literal[
        "adaptation",
        "arrangement",
        "based on",
        "included works",
        "lyrical quotation",
        "medley",
        "musical quotation",
        "named after work",
        "orchestration",
        "other version",
        "parts",
        "revision of",
    ]
    ordering_key: NotRequired[int]
    work: Work


class Work(TypedDict):
    attributes: list[str]
    disambiguation: str
    id: str
    iswcs: list[str]
    language: str | None
    languages: list[str]
    title: str
    type: str | None
    type_id: str | None
    artist_relations: NotRequired[list[ArtistRelation]]
    url_relations: NotRequired[list[UrlRelation]]
    work_relations: NotRequired[list[WorkRelation]]


class Recording(TypedDict):
    aliases: list[Alias]
    artist_credit: list[ArtistCredit]
    disambiguation: str
    id: str
    isrcs: list[str]
    length: int | None
    title: str
    video: bool
    artist_relations: NotRequired[list[ArtistRelation]]
    first_release_date: NotRequired[str]
    genres: NotRequired[list[Genre]]
    tags: NotRequired[list[Tag]]
    url_relations: NotRequired[list[UrlRelation]]
    work_relations: NotRequired[list[WorkRelation]]


class Track(TypedDict):
    artist_credit: list[ArtistCredit]
    id: str
    length: int | None
    number: str
    position: int
    recording: Recording
    title: str


class Medium(TypedDict):
    format: str | None
    format_id: str | None
    id: str
    position: int
    title: str
    track_count: int
    data_tracks: NotRequired[list[Track]]
    pregap: NotRequired[Track]
    track_offset: NotRequired[int]
    tracks: NotRequired[list[Track]]


class ReleaseRelationRelease(TypedDict):
    artist_credit: list[ArtistCredit]
    barcode: str | None
    country: str | None
    date: str
    disambiguation: str
    id: str
    media: list[Medium]
    packaging: ReleasePackaging | None
    packaging_id: str | None
    quality: ReleaseQuality
    release_events: list[ReleaseEvent]
    release_group: ReleaseGroup
    status: ReleaseStatus | None
    status_id: str | None
    text_representation: TextRepresentation
    title: str


class ReleaseRelation(RelationBase):
    type: Literal["remaster", "transl-tracklisting", "replaced by"]
    release: ReleaseRelationRelease


class Release(TypedDict):
    aliases: list[Alias]
    artist_credit: list[ArtistCredit]
    asin: str | None
    barcode: str | None
    cover_art_archive: CoverArtArchive
    disambiguation: str
    genres: list[Genre]
    id: str
    label_info: list[LabelInfo]
    media: list[Medium]
    packaging: ReleasePackaging | None
    packaging_id: str | None
    quality: ReleaseQuality
    release_group: ReleaseGroup
    status: ReleaseStatus | None
    status_id: str | None
    tags: list[Tag]
    text_representation: TextRepresentation
    title: str
    artist_relations: NotRequired[list[ArtistRelation]]
    country: NotRequired[str | None]
    date: NotRequired[str]
    release_events: NotRequired[list[ReleaseEvent]]
    release_relations: NotRequired[list[ReleaseRelation]]
    url_relations: NotRequired[list[UrlRelation]]


def require_one_of(*keys: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    required = frozenset(keys)

    def deco(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # kwargs is a real dict at runtime; safe to inspect here
            if not required & kwargs.keys():
                required_str = ", ".join(sorted(required))
                raise ValueError(
                    f"At least one of {required_str} filter is required"
                )
            return func(*args, **kwargs)

        return wrapper

    return deco


@dataclass
class MusicBrainzAPI(RequestHandler):
    """High-level interface to the MusicBrainz WS/2 API.

    Responsibilities:

    - Configure the API host and request rate from application configuration.
    - Offer helpers to fetch common entity types and to run searches.
    - Normalize MusicBrainz responses so relation lists are grouped by target
      type for easier downstream consumption.

    Documentation: https://musicbrainz.org/doc/MusicBrainz_API
    """

    api_host: str = field(init=False)
    rate_limit: float = field(init=False)

    def __post_init__(self) -> None:
        mb_config = config["musicbrainz"]
        mb_config.add(
            {
                "host": "musicbrainz.org",
                "https": False,
                "ratelimit": 1,
                "ratelimit_interval": 1,
            }
        )

        hostname = mb_config["host"].as_str()
        if hostname == "musicbrainz.org":
            self.api_host, self.rate_limit = "https://musicbrainz.org", 1.0
        else:
            https = mb_config["https"].get(bool)
            self.api_host = f"http{'s' if https else ''}://{hostname}"
            self.rate_limit = (
                mb_config["ratelimit"].get(int)
                / mb_config["ratelimit_interval"].as_number()
            )

    @cached_property
    def api_root(self) -> str:
        return f"{self.api_host}/ws/2"

    def create_session(self) -> LimiterTimeoutSession:
        return LimiterTimeoutSession(per_second=self.rate_limit)

    def request(self, *args, **kwargs) -> Response:
        """Ensure all requests specify JSON response format by default."""
        kwargs.setdefault("params", {})
        kwargs["params"]["fmt"] = "json"
        return super().request(*args, **kwargs)

    def _get_resource(
        self, resource: str, includes: list[str] | None = None, **kwargs
    ) -> JSONDict:
        """Retrieve and normalize data from the API resource endpoint.

        If requested, includes are appended to the request. The response is
        passed through a normalizer that groups relation entries by their
        target type so that callers receive a consistently structured mapping.
        """
        if includes:
            kwargs["inc"] = "+".join(includes)

        return self._normalize_data(
            self.get_json(f"{self.api_root}/{resource}", params=kwargs)
        )

    def _lookup(
        self, entity: Entity, id_: str, **kwargs: Unpack[LookupKwargs]
    ) -> Any:
        return self._get_resource(f"{entity}/{id_}", **kwargs)

    def _browse(self, entity: Entity, **kwargs) -> list[Any]:
        return self._get_resource(entity, **kwargs).get(f"{entity}s", [])

    @staticmethod
    def format_search_term(field: str, term: str) -> str:
        """Format a search term for the MusicBrainz API.

        See https://lucene.apache.org/core/4_3_0/queryparser/org/apache/lucene/queryparser/classic/package-summary.html
        """
        if not (term := term.lower().strip()):
            return ""

        term = LUCENE_SPECIAL_CHAR_PAT.sub(r"\\\1", term)
        if field:
            term = f"{field}:({term})"

        return term

    def search(
        self,
        entity: Entity,
        filters: dict[str, str],
        **kwargs: Unpack[SearchKwargs],
    ) -> list[JSONDict]:
        """Search for MusicBrainz entities matching the given filters.

        * Query is constructed by combining the provided filters using AND logic
        * Each filter key-value pair is formatted as 'key:"value"' unless
          - 'key' is empty, in which case only the value is used, '"value"'
          - 'value' is empty, in which case the filter is ignored
        * Values are lowercased and stripped of whitespace.
        """
        query = " ".join(
            filter(None, starmap(self.format_search_term, filters.items()))
        )
        log.debug("Searching for MusicBrainz {}s with: {!r}", entity, query)
        kwargs["query"] = query
        return self._get_resource(entity, **kwargs)[f"{entity}s"]

    def get_release(self, id_: str, **kwargs: Unpack[LookupKwargs]) -> Release:
        """Retrieve a release by its MusicBrainz ID."""
        kwargs.setdefault("includes", RELEASE_INCLUDES)
        return self._lookup("release", id_, **kwargs)

    def get_recording(
        self, id_: str, **kwargs: Unpack[LookupKwargs]
    ) -> Recording:
        """Retrieve a recording by its MusicBrainz ID."""
        kwargs.setdefault("includes", RECORDING_INCLUDES)
        return self._lookup("recording", id_, **kwargs)

    def get_work(self, id_: str, **kwargs: Unpack[LookupKwargs]) -> Work:
        """Retrieve a work by its MusicBrainz ID."""
        return self._lookup("work", id_, **kwargs)

    @require_one_of("artist", "collection", "release", "work")
    def browse_recordings(
        self, **kwargs: Unpack[BrowseRecordingsKwargs]
    ) -> list[Recording]:
        """Browse recordings related to the given entities.

        At least one of artist, collection, release, or work must be provided.
        """
        return self._browse("recording", **kwargs)

    @require_one_of("artist", "collection", "release")
    def browse_release_groups(
        self, **kwargs: Unpack[BrowseReleaseGroupsKwargs]
    ) -> list[ReleaseGroup]:
        """Browse release groups related to the given entities.

        At least one of artist, collection, or release must be provided.
        """
        return self._get_resource("release-group", **kwargs)["release-groups"]

    @singledispatchmethod
    @classmethod
    def _normalize_data(cls, data: Any) -> Any:
        """Normalize MusicBrainz relation structures into easier-to-use shapes.

        This default handler is a no-op that returns non-container values
        unchanged. Specialized handlers for sequences and mappings perform the
        actual transformations described below.
        """
        return data

    @_normalize_data.register(list)
    @classmethod
    def _(cls, data: list[Any]) -> list[Any]:
        """Apply normalization to each element of a sequence recursively.

        Sequences received from the MusicBrainz API may contain nested mappings
        that require transformation. This handler maps the normalization step
        over the sequence and preserves order.
        """
        return [cls._normalize_data(i) for i in data]

    @_normalize_data.register(dict)
    @classmethod
    def _(cls, data: JSONDict) -> JSONDict:
        """Transform mappings by regrouping relationships and normalizing keys.

        When a mapping contains a generic 'relations' list, entries are grouped
        by their 'target-type' and placed under keys like
        '<target-type>_relations' with the 'target-type' field removed from each
        entry. All other mapping keys have hyphens converted to underscores and
        their values are normalized recursively to ensure a consistent shape
        throughout the payload.
        """
        output_data = {}
        for k, v in list(data.items()):
            if k == "relations":
                get_target_type = operator.methodcaller("get", "target-type")
                for target_type, group in groupby(
                    sorted(v, key=get_target_type), get_target_type
                ):
                    relations = [
                        {k: v for k, v in item.items() if k != "target-type"}
                        for item in group
                    ]
                    output_data[f"{target_type}_relations"] = (
                        cls._normalize_data(relations)
                    )
            else:
                output_data[k.replace("-", "_")] = cls._normalize_data(v)
        return output_data


class MusicBrainzAPIMixin:
    """Mixin that provides a cached MusicBrainzAPI helper instance."""

    @cached_property
    def mb_api(self) -> MusicBrainzAPI:
        return MusicBrainzAPI()
