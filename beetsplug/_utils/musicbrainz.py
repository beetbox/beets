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

        return self._group_relations(
            self.get_json(f"{self.api_root}/{resource}", params=kwargs)
        )

    def _lookup(
        self, entity: Entity, id_: str, **kwargs: Unpack[LookupKwargs]
    ) -> JSONDict:
        return self._get_resource(f"{entity}/{id_}", **kwargs)

    def _browse(self, entity: Entity, **kwargs) -> list[JSONDict]:
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

    def get_release(self, id_: str, **kwargs: Unpack[LookupKwargs]) -> JSONDict:
        """Retrieve a release by its MusicBrainz ID."""
        kwargs.setdefault("includes", RELEASE_INCLUDES)
        return self._lookup("release", id_, **kwargs)

    def get_recording(
        self, id_: str, **kwargs: Unpack[LookupKwargs]
    ) -> JSONDict:
        """Retrieve a recording by its MusicBrainz ID."""
        kwargs.setdefault("includes", RECORDING_INCLUDES)
        return self._lookup("recording", id_, **kwargs)

    def get_work(self, id_: str, **kwargs: Unpack[LookupKwargs]) -> JSONDict:
        """Retrieve a work by its MusicBrainz ID."""
        return self._lookup("work", id_, **kwargs)

    @require_one_of("artist", "collection", "release", "work")
    def browse_recordings(
        self, **kwargs: Unpack[BrowseRecordingsKwargs]
    ) -> list[JSONDict]:
        """Browse recordings related to the given entities.

        At least one of artist, collection, release, or work must be provided.
        """
        return self._browse("recording", **kwargs)

    @require_one_of("artist", "collection", "release")
    def browse_release_groups(
        self, **kwargs: Unpack[BrowseReleaseGroupsKwargs]
    ) -> list[JSONDict]:
        """Browse release groups related to the given entities.

        At least one of artist, collection, or release must be provided.
        """
        return self._get_resource("release-group", **kwargs)["release-groups"]

    @singledispatchmethod
    @classmethod
    def _group_relations(cls, data: Any) -> Any:
        """Normalize MusicBrainz 'relations' into type-keyed fields recursively.

        This helper rewrites payloads that use a generic 'relations' list into
        a structure that is easier to consume downstream. When a mapping
        contains 'relations', those entries are regrouped by their 'target-type'
        and stored under keys like '<target-type>-relations'. The original
        'relations' key is removed to avoid ambiguous access patterns.

        The transformation is applied recursively so that nested objects and
        sequences are normalized consistently, while non-container values are
        left unchanged.
        """
        return data

    @_group_relations.register(list)
    @classmethod
    def _(cls, data: list[Any]) -> list[Any]:
        return [cls._group_relations(i) for i in data]

    @_group_relations.register(dict)
    @classmethod
    def _(cls, data: JSONDict) -> JSONDict:
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
                    data[f"{target_type}-relations"] = cls._group_relations(
                        relations
                    )
                data.pop("relations")
            else:
                data[k] = cls._group_relations(v)
        return data


class MusicBrainzAPIMixin:
    """Mixin that provides a cached MusicBrainzAPI helper instance."""

    @cached_property
    def mb_api(self) -> MusicBrainzAPI:
        return MusicBrainzAPI()
