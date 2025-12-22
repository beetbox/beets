from __future__ import annotations

import operator
from dataclasses import dataclass, field
from functools import cached_property, singledispatchmethod
from itertools import groupby
from typing import TYPE_CHECKING, Any

from requests_ratelimiter import LimiterMixin

from beets import config, logging

from .requests import RequestHandler, TimeoutAndRetrySession

if TYPE_CHECKING:
    from .._typing import JSONDict

log = logging.getLogger(__name__)


class LimiterTimeoutSession(LimiterMixin, TimeoutAndRetrySession):
    pass


@dataclass
class MusicBrainzAPI(RequestHandler):
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

    def create_session(self) -> LimiterTimeoutSession:
        return LimiterTimeoutSession(per_second=self.rate_limit)

    def get_entity(
        self, entity: str, includes: list[str] | None = None, **kwargs
    ) -> JSONDict:
        if includes:
            kwargs["inc"] = "+".join(includes)

        return self._group_relations(
            self.get_json(
                f"{self.api_host}/ws/2/{entity}",
                params={**kwargs, "fmt": "json"},
            )
        )

    def search_entity(
        self, entity: str, filters: dict[str, str], **kwargs
    ) -> list[JSONDict]:
        """Search for MusicBrainz entities matching the given filters.

        * Query is constructed by combining the provided filters using AND logic
        * Each filter key-value pair is formatted as 'key:"value"' unless
          - 'key' is empty, in which case only the value is used, '"value"'
          - 'value' is empty, in which case the filter is ignored
        * Values are lowercased and stripped of whitespace.
        """
        query = " AND ".join(
            ":".join(filter(None, (k, f'"{_v}"')))
            for k, v in filters.items()
            if (_v := v.lower().strip())
        )
        log.debug("Searching for MusicBrainz {}s with: {!r}", entity, query)
        kwargs["query"] = query
        return self.get_entity(entity, **kwargs)[f"{entity}s"]

    def get_release(self, id_: str, **kwargs) -> JSONDict:
        return self.get_entity(f"release/{id_}", **kwargs)

    def get_recording(self, id_: str, **kwargs) -> JSONDict:
        return self.get_entity(f"recording/{id_}", **kwargs)

    def browse_recordings(self, **kwargs) -> list[JSONDict]:
        return self.get_entity("recording", **kwargs)["recordings"]

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
    @cached_property
    def mb_api(self) -> MusicBrainzAPI:
        return MusicBrainzAPI()
