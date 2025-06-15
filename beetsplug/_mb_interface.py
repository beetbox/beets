import json
import re
from typing import TYPE_CHECKING, Literal, Optional, Union

from mbzero import mbzrequest as mbzr

import beets
from beets.util.rate_limiter import RateLimiter

if TYPE_CHECKING:
    from ._typing import JSONDict


class MbInterface:
    """An interface for sending requests using MusicBrainz API"""

    def __init__(self, hostname: str, https: bool, rate_limiter: RateLimiter):
        self.hostname = hostname
        self.https = https
        self.rate_limiter = rate_limiter
        self.useragent = f"beets/{beets.__version__} (https://beets.io/)"

    def _lookup(
        self,
        entity_type: str,
        mbid: str,
        includes: list[str],
    ) -> bytes:
        """Send a lookup request to the configured MusicBrainz API to get information
        on a single entity

        :param entity_type: The type of entity to look up
        :param mbid: The MusicBrainz ID of the entity to look up
        :param includes: List of parameters to request more information to be included
            about the entity
        :return: The response as bytes
        :raises mbzerror.MbzWebServiceError: if the request did not succeed
        """
        with self.rate_limiter:
            return self._send(
                mbzr.MbzRequestLookup(
                    self.useragent, entity_type, mbid, includes
                ),
            )

    def _browse(
        self,
        lookup_entity_type: str,
        mbid: str,
        linked_entities_type: str,
        includes: Optional[list[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> bytes:
        """Send a browse request to the configured MusicBrainz API to get entities
        linked to looked up one

        :param lookup_entity_type: The type of entity to look up
        :param mbid: The MusicBrainz ID of the entity to look up
        :param linked_entities_type: The type of linked entities to find
        :param includes: List of parameters to request more information to be included
            about the entity
        :param limit: The number of entities that should be returned
        :param offset: Offset used for paging through more than one page of results
        :return: The response as bytes
        :raises mbzerror.MbzWebServiceError: if the request did not succeed
        """
        if includes is None:
            includes = []

        with self.rate_limiter:
            return self._send(
                mbzr.MbzRequestBrowse(
                    self.useragent,
                    linked_entities_type,
                    lookup_entity_type,
                    mbid,
                    includes,
                ),
                limit=limit,
                offset=offset,
            )

    def _search(
        self,
        entity_type: str,
        query: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        **fields,
    ) -> bytes:
        """Send a search request to the configured MusicBrainz API to search entities
        based on a query

        :param entity_type: The type of entity to look up
        :param query: The query in the Lucene Search syntax
        :param limit: The number of entities that should be returned
        :param offset: Offset used for paging through more than one page of results
        :return: The response as bytes
        :raises mbzerror.MbzWebServiceError: if the request did not succeed
        """

        with self.rate_limiter:
            return self._send(
                mbzr.MbzRequestSearch(self.useragent, entity_type, query),
                limit=limit,
                offset=offset,
            )

    def _send(
        self,
        mbr: Union[
            mbzr.MbzRequestLookup, mbzr.MbzRequestSearch, mbzr.MbzRequestBrowse
        ],
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> bytes:
        """Send the request

        :param mbr: The request object
        :param limit: The number of entities that should be returned
        :param offset: Offset used for paging through more than one page of results
        :return: The response as bytes
        :raises mbzerror.MbzWebServiceError: if the request did not succeed
        """
        if self.hostname:
            scheme = "https" if self.https else "http"
            mbr.set_url(f"{scheme}://{self.hostname}/ws/2")
        opts = {}
        if limit is not None:
            opts["limit"] = limit
        if offset is not None:
            opts["offset"] = offset
        return mbr.send(opts=opts)

    def _make_query(self, fields: Optional[dict[str, str]] = None) -> str:
        """Make a Lucene Query string from a dict of fields

        :param fields: Dict of field keys and values used to build the query.
            Values will be properly escaped.
        :return: The built Lucene Query string
        """
        if fields is None:
            fields = {}

        # Encode the query terms as a Lucene query string.
        lucene_special = r'([+\-&|!(){}\[\]\^"~*?:\\\/])'
        query_parts = []

        for key, value in fields.items():
            # Escape Lucene's special characters.
            if value := re.sub(lucene_special, r"\\\1", value):
                value = value.lower()  # avoid AND / OR
                query_parts.append(f"{key}:({value})")

        if full_query := " ".join(query_parts).strip():
            return full_query
        else:
            raise ValueError("at least one query term is required")

    @staticmethod
    def _remove_none_values(data):
        """Iterate recursively over a Python object to remove all None values in
        dicts
        """
        if isinstance(data, dict):
            return {
                key: MbInterface._remove_none_values(value)
                for key, value in data.items()
                if value is not None
            }
        elif isinstance(data, list):
            return [MbInterface._remove_none_values(item) for item in data]
        else:
            return data

    @staticmethod
    def _parse_and_clean_json(data: bytes) -> "JSONDict":
        """Parse the JSON data and remove all None values in dicts.
        This is needed as the MusicBrainz JSON data contains None values instead of
        simply not setting them in dictionaries.
        This is also different from the their XML data which only contains filled
        values.

        :param data: JSON data as bytes
        """
        return MbInterface._remove_none_values(json.loads(data))

    def browse_recordings(
        self,
        lookup_entity_type: Literal["artist", "collection", "release", "work"],
        mbid: str,
        includes: Optional[list[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> "JSONDict":
        """Browse recordings linked to an entity

        :param lookup_entity_type: The type of entity whose recordings are to be browsed
        :param mbid: The MusicBrainz ID of the entity
        :param includes: List of parameters to request more information to be included
            about the recordings
        :param limit: The number of recordings that should be returned
        :param offset: Offset used for paging through more than one page of results
        :return: The JSON-decoded response as an object
        :raises mbzerror.MbzWebServiceError: if the request did not succeed
        """
        if includes is None:
            includes = []

        return MbInterface._parse_and_clean_json(
            self._browse(
                lookup_entity_type,
                mbid,
                "recording",
                includes,
                limit=limit,
                offset=offset,
            )
        )

    def browse_release_groups(
        self,
        lookup_entity_type: Literal["artist", "collection", "release"],
        mbid: str,
        includes: Optional[list[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> "JSONDict":
        """Browse release-groups linked to an entity

        :param lookup_entity_type: The type of entity whose release-groups are to be
            browsed
        :param mbid: The MusicBrainz ID of the entity
        :param includes: List of parameters to request more information to be included
            about the release-groups
        :param limit: The number of release-groups that should be returned
        :param offset: Offset used for paging through more than one page of results
        :return: The JSON-decoded response as an object
        :raises mbzerror.MbzRequestError: if the request did not succeed
        """
        if includes is None:
            includes = []

        return MbInterface._parse_and_clean_json(
            self._browse(
                lookup_entity_type,
                mbid,
                "release-group",
                includes,
                limit=limit,
                offset=offset,
            )
        )

    def get_release_by_id(
        self,
        mbid: str,
        includes: Optional[list[str]] = None,
    ) -> "JSONDict":
        """Get a release from its ID

        :param mbid: The MusicBrainz ID of the release
        :param includes: List of parameters to request more information to be included
            about the release
        :return: The JSON-decoded response as an object
        :raises mbzerror.MbzWebServiceError: if the request did not succeed
        """
        if includes is None:
            includes = []

        return MbInterface._parse_and_clean_json(
            self._lookup(
                "release",
                mbid,
                includes,
            )
        )

    def get_recording_by_id(
        self,
        mbid: str,
        includes: Optional[list[str]] = None,
    ) -> "JSONDict":
        """Get a recording from its ID

        :param mbid: The MusicBrainz ID of the entity
        :param includes: List of parameters to request more information to be included
            about the recording
        :return: The JSON-decoded response as an object
        :raises mbzerror.MbzWebServiceError: if the request did not succeed
        """
        if includes is None:
            includes = []

        return MbInterface._parse_and_clean_json(
            self._lookup(
                "recording",
                mbid,
                includes,
            )
        )

    def get_work_by_id(
        self,
        mbid: str,
        includes: Optional[list[str]] = None,
    ) -> "JSONDict":
        """Get a work from its ID

        :param mbid: The MusicBrainz ID of the entity
        :param includes: List of parameters to request more information to be included
            about the work
        :return: The JSON-decoded response as an object
        :raises mbzerror.MbzRequestError: if the request did not succeed
        """
        if includes is None:
            includes = []

        return MbInterface._parse_and_clean_json(
            self._lookup(
                "work",
                mbid,
                includes,
            )
        )

    def search_releases(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        **fields: str,
    ) -> "JSONDict":
        """Search for releases using a query

        :param limit: The number of releases that should be returned
        :param offset: Offset used for paging through more than one page of results
        :param fields: Dict of fields composing the search query
        :return: The JSON-decoded response as an object
        :raises mbzerror.MbzWebServiceError: if the request did not succeed
        """
        return MbInterface._parse_and_clean_json(
            self._search(
                "release",
                query=self._make_query(fields),
                limit=limit,
                offset=offset,
            )
        )

    def search_recordings(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        **fields: str,
    ) -> "JSONDict":
        """Search for recordings using a query

        :param limit: The number of recordings that should be returned
        :param offset: Offset used for paging through more than one page of results
        :param fields: Dict of fields composing the search query
        :return: The JSON-decoded response as an object
        :raises mbzerror.MbzWebServiceError: if the request did not succeed
        """
        return MbInterface._parse_and_clean_json(
            self._search(
                "recording",
                query=self._make_query(fields),
                limit=limit,
                offset=offset,
            )
        )


class SharedMbInterface:
    """Singleton holding a shared MbInterface.
    This can be used to use the same configuration, rate limiting, etc. between
    multiple plugins.
    """

    def __new__(cls):
        """Create the singleton"""
        if not hasattr(cls, "instance"):
            cls.instance = super(SharedMbInterface, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        mb_config = beets.config["musicbrainz"]
        mb_config.add(
            {
                "host": "musicbrainz.org",
                "https": False,
                "ratelimit": 1,
                "ratelimit_interval": 1,
            }
        )

        hostname = mb_config["host"].as_str()
        https = mb_config["https"].get(bool)
        # Force https usage for default MusicBrainz server
        if hostname == "musicbrainz.org":
            https = True

        self.mb_interface = MbInterface(
            hostname,
            https,
            RateLimiter(
                reqs_per_interval=mb_config["ratelimit"].get(int),
                interval_sec=mb_config["ratelimit_interval"].as_number(),
            ),
        )

    def get(self) -> MbInterface:
        return self.mb_interface
