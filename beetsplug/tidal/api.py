from __future__ import annotations

from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING, TypeVar

import requests

from beets.logging import getLogger
from beetsplug._utils.requests import RateLimitAdapter, TimeoutAndRetrySession

from .authenticate import TidalToken

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .api_types import AlbumDocument, Document, TrackDocument

log = getLogger("tidal.api")


API_BASE = "https://openapi.tidal.com/v2"


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
        log.debug("Tidal request: %s %s", method, url)
        kwargs["auth"] = self.token
        res = super().request(method, url, *args, **kwargs)
        # 401 = Needs refreshing
        if res.status_code == 401:
            self._refresh_token()
            return self.request(method, url, *args, **kwargs)
        elif res.status_code == 429:
            self._handle_rate_limit(res)
            return self.request(method, url, *args, **kwargs)

        return res

    def _handle_rate_limit(self, response: requests.Response) -> None:
        remaining = int(response.headers.get("Retry-After", 0))
        if remaining > 0:
            log.warning(
                "Rate limit exceeded. Retrying after %s seconds.", remaining
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
        params: dict | None = None,
        **kwargs,
    ) -> Document:
        """
        Perform a GET request to the Tidal API with pagination resolution.

        This handles both top-level pagination and nested relationship pagination.

        Returns
        -------
            tuple: (data_items, included_lookup, last_links)
        """
        include = include or []
        params = params or {}

        doc: Document = {
            "data": [],
            "included": [],
            "links": {"next": url},
        }

        while next := doc.get("links", {}).get("next"):
            res = self.request(
                method="GET",
                url=next,
                params={**params, "include": include},
                **kwargs,
            )
            page_doc = res.json()
            doc = self._merge_multiresource_pagination(doc, page_doc)

        # Dedupe include
        doc["included"] = list(
            {
                (item["type"], item["id"]): item for item in doc["included"]
            }.values()
        )
        return doc

    def _merge_multiresource_pagination(
        self,
        a: Document,
        b: Document,
    ) -> Document:
        """
        Merge of b into a, following JSON:API spec rules.

        - Appends data arrays
        - Deduplicates included by (type,id)
        - Updates links (b overrides a)
        - Merges meta objects
        """
        a["included"] = a.get("included", [])
        a["links"] = a.get("links", {})

        # Append data (primary resources)
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

        # Merge meta (deep merge if needed)
        if "meta" in b:
            if "meta" not in a:
                a["meta"] = b["meta"]
            else:
                a["meta"].update(b["meta"])

        return a

    def _refresh_token(self) -> None:
        """Refresh the Tidal token.

        This function will refresh the Tidal token using the refresh token.
        It will update the token in place.
        """
        log.debug("Refreshing expired Tidal token...")
        res = super().request(
            self,
            "POST",
            "https://auth.tidal.com/v1/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": self.token.refresh_token,
            },
        )
        try:
            res.raise_for_status()
        except requests.HTTPError as e:
            log.error(res.text, stack_info=False)
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
    ):
        """Search results for a query.

        https://tidal-music.github.io/tidal-api-reference/#/searchResults
        """
        params = {
            "explicitFilter": explicit_filter,
            "countryCode": country_code,
            "include": include or [],
        }

        return self.session.get(
            f"{API_BASE}/searchResults/{query}", params=params
        )

    def get_tracks(
        self,
        # filters
        ids: list[str] | str | None = None,
        isrcs: list[str] | str | None = None,
        *,
        include: list[str] | str | None = None,
        country_code: str = "US",
    ) -> TrackDocument:
        """Fetch tracks resolving pagination and included items.

        Should only ever be called with 20 items as
        tidal does not support more per requests. This does not mean more than
        20 cant be returned.

        https://tidal-music.github.io/tidal-api-reference/#/tracks/get_tracks
        """
        params: dict[str, str | list[str]] = {}
        if country_code:
            params["countryCode"] = country_code
        if ids:
            params["filter[id]"] = ids
        if isrcs:
            params["filter[isrc]"] = isrcs

        return self.session.get_paginated(
            f"{API_BASE}/tracks",
            include,
            params=params,
        )

    def get_albums(
        self,
        # filters
        ids: list[str] | str | None = None,
        barcode_ids: list[str] | str | None = None,
        *,
        include: list[str] | str | None = None,
        country_code: str = "US",
    ) -> AlbumDocument:
        """Fetch Albums resolving pagination and included items.

        Should only ever be called with 20 items as tidal does not support more per
        requests. This does not mean more than 20 cant be returned.

        https://tidal-music.github.io/tidal-api-reference/#/albums/get_albums
        """
        params: dict[str, str | list[str]] = {}
        if country_code:
            params["countryCode"] = country_code
        if ids:
            params["filter[id]"] = ids
        if barcode_ids:
            params["filter[barcodeId]"] = barcode_ids

        return self.session.get_paginated(
            f"{API_BASE}/albums",
            include,
            params=params,
        )


A = TypeVar("A")


def chunk_list(lst: list[A], chunk_size: int) -> Iterable[list[A]]:
    """
    Chunk a list into smaller lists of the specified size.
    """
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]
