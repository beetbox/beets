from __future__ import annotations

import urllib.parse
from itertools import islice, zip_longest
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING, Any, TypeVar

import requests

from beets.logging import getLogger
from beetsplug._utils.requests import RateLimitAdapter, TimeoutAndRetrySession

from .authenticate import TidalToken

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .api_types import (
        AlbumDocument,
        Document,
        SearchDocument,
        TrackDocument,
    )

    T = TypeVar("T")

log = getLogger("beets.tidal")


API_BASE = "https://openapi.tidal.com/v2"
MAX_FILTER_SIZE = 20


def _batched(iterable: Iterable[T], n: int) -> Iterable[list[T]]:
    # FIXME: Replace with itertools.batched once
    # we upgrade to python > 3.12
    it = iter(iterable)
    while batch := list(islice(it, n)):
        yield batch


class TidalSession(TimeoutAndRetrySession):
    """A request Session configured for Tidal.

    Automatically attaches the auth token and refreshes
    it as needed. Use for making multiple requests to the API.
    """

    client_id: str
    token_path: Path

    def __init__(self, client_id: str, token_path: str | Path) -> None:
        super().__init__()
        self.client_id = client_id
        self.token_path = Path(token_path)

        # Mount rate limit adapter only for Tidal
        adapter = RateLimitAdapter(rate_limit=0.25)  # ~4/s
        self.mount("https://auth.tidal.com/", adapter)
        self.mount(API_BASE, adapter)

    _token: TidalToken | None = None

    @property
    def token(self):
        if self._token is None:
            self._token = TidalToken.from_file(self.token_path)
        return self._token

    def request(
        self, method: str | bytes, url: str | bytes, *args, **kwargs
    ) -> requests.Response:
        """Send a request with token authentication.

        Automatically handles token expiration and server-side token
        rejection by refreshing and retrying once per failure mode.
        """
        if isinstance(url, str) and not url.startswith("http"):
            url = API_BASE + url

        if self.token.is_expired:
            self._refresh_token()
        kwargs["auth"] = self.token
        try:
            # TimeoutAndRetrySession raises on bad requests
            res = super().request(method, url, *args, **kwargs)
        except requests.exceptions.HTTPError as e:
            res = e.response

            # 401 = Needs refreshing
            if res.status_code == 401:
                self._refresh_token()
                return self.request(method, url, *args, **kwargs)
            elif res.status_code == 429:
                self._handle_rate_limit(res)
                return self.request(method, url, *args, **kwargs)
            raise

        return res

    def _handle_rate_limit(self, response: requests.Response) -> None:
        remaining = int(response.headers.get("Retry-After", 0))
        if remaining > 0:
            log.warning(
                "Rate limit exceeded. Retrying after {0} seconds.", remaining
            )
            sleep(remaining)
        else:
            raise Exception(
                "Rate limit handling failed: Retry-After header is missing or invalid"
            )
        return

    def get_paginated(
        self,
        url: str,
        include: list[str] | str | None = None,
        params: dict[str, Any] | None = None,
        **kwargs,
    ) -> Document[list[Any]]:
        """
        Perform a GET request to the Tidal API with pagination resolution.
        """
        include = include or []
        params = params or {}

        doc: Document[list[Any]] = {
            "data": [],
            "included": [],
            "links": {"next": url},
        }

        while next := doc.get("links", {}).get("next"):
            res = self.get(
                url=next,
                params={**params, "include": include},
                **kwargs,
            )
            page_doc = res.json()
            doc = self.merge_multiresource_pagination(doc, page_doc)

        # Dedupe include
        doc["included"] = list(
            {
                (item["type"], item["id"]): item
                for item in doc.get("included", [])
            }.values()
        )
        return doc

    @staticmethod
    def merge_multiresource_pagination(
        a: Document[list[T]],
        b: Document[list[T]],
    ) -> Document[list[T]]:
        """
        Merge of b into a, following JSON:API spec rules.

        - Appends data arrays
        - Deduplicates included by (type,id)
        - Updates links (b overrides a)
        - Merges meta objects
        """
        a["included"] = a.get("included", [])
        a["links"] = a.get("links", {})

        a["data"].extend(b["data"])

        # Merge included with deduplication
        seen = {(item["type"], item["id"]) for item in a["included"]}
        for item in b.get("included", []):
            key = (item["type"], item["id"])
            if key not in seen:
                seen.add(key)
                a["included"].append(item)

        # Update pagination links (final state wins)
        a["links"] = b.get("links", {})
        return a

    def _refresh_token(self) -> None:
        """Refresh the Tidal token.

        This function will refresh the Tidal token using the refresh token.
        It will update the token in place.
        """
        log.debug("Refreshing expired Tidal token...")
        try:
            res = super().request(
                "POST",
                "https://auth.tidal.com/v1/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "refresh_token": self.token.refresh_token,
                },
            )
        except requests.HTTPError as e:
            log.error(e.response.text, stack_info=False)
            raise e

        # We update and dont override as the response might not always
        # contain all information
        self.token.update(res.json())
        self.token.save_to(self.token_path)


class TidalAPI:
    session: TidalSession

    def __init__(self, session: TidalSession) -> None:
        self.session = session

    def search_results(
        self,
        query: str,
        *,
        explicit_filter: str = "INCLUDE",
        include: list[str] | None = None,
        country_code: str = "US",
    ) -> SearchDocument:
        """Search results for a query.

        https://tidal-music.github.io/tidal-api-reference/#/searchResults
        """
        params = {
            "explicitFilter": explicit_filter,
            "countryCode": country_code,
            "include": include or [],
        }

        return self.session.get(
            f"{API_BASE}/searchResults/{urllib.parse.quote(query)}",
            params=params,
        ).json()

    def get_tracks(
        self,
        ids: list[str] | None = None,
        isrcs: list[str] | None = None,
        include: list[str] | None = None,
        country_code: str = "US",
    ) -> TrackDocument:
        """Fetch tracks resolving pagination and included items.

        https://tidal-music.github.io/tidal-api-reference/#/tracks/get_tracks
        """
        ids = ids or []
        isrcs = isrcs or []

        # Tidal allows at max 20 filters per request. This needs a bit of extra
        # logic sadly.
        doc: TrackDocument = {
            "data": [],
            "included": [],
        }
        for id_batch, isrc_batch in zip_longest(
            _batched(ids, MAX_FILTER_SIZE),
            _batched(isrcs, MAX_FILTER_SIZE),
            fillvalue=(),
        ):
            params: dict[str, Any] = {"countryCode": country_code}
            if id_batch:
                params["filter[id]"] = id_batch
            if isrc_batch:
                params["filter[isrc]"] = isrc_batch

            doc = self.session.merge_multiresource_pagination(
                doc,
                self.session.get_paginated(
                    f"{API_BASE}/tracks", include, params=params
                ),
            )

        return doc

    def get_albums(
        self,
        ids: list[str] | None = None,
        barcode_ids: list[str] | None = None,
        include: list[str] | None = None,
        country_code: str = "US",
    ) -> AlbumDocument:
        """Fetch Albums resolving pagination and included items.

        https://tidal-music.github.io/tidal-api-reference/#/albums/get_albums
        """
        ids = ids or []
        barcode_ids = barcode_ids or []

        # Tidal allows at max 20 filters per request. This needs a bit of extra
        # logic sadly.
        doc: AlbumDocument = {
            "data": [],
            "included": [],
        }
        for id_batch, barcode_batch in zip_longest(
            _batched(ids, MAX_FILTER_SIZE),
            _batched(barcode_ids, MAX_FILTER_SIZE),
            fillvalue=(),
        ):
            params: dict[str, Any] = {"countryCode": country_code}
            if id_batch:
                params["filter[id]"] = id_batch
            if barcode_batch:
                params["filter[barcodeId]"] = barcode_batch

            doc = self.session.merge_multiresource_pagination(
                doc,
                self.session.get_paginated(
                    f"{API_BASE}/albums", include, params=params
                ),
            )

        return doc
