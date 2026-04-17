from __future__ import annotations

import urllib.parse
import webbrowser
from functools import cached_property
from itertools import islice, zip_longest
from typing import TYPE_CHECKING, Any, TypeVar

from beets import ui
from beets.logging import getLogger
from beetsplug._utils.requests import RequestHandler
from beetsplug.tidal.session import TidalSession

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


class TidalAPI(RequestHandler):
    def __init__(self, client_id: str, token_path: str) -> None:
        self.client_id = client_id
        self.token_path = token_path

    @cached_property
    def session(self) -> TidalSession:
        return TidalSession(self.client_id, self.token_path)

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

        return self.get_json(
            f"{API_BASE}/searchResults/{urllib.parse.quote(query)}",
            params=params,
        )

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

            doc = self.merge_multiresource_pagination(
                doc,
                self.get_paginated(
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

            doc = self.merge_multiresource_pagination(
                doc,
                self.get_paginated(
                    f"{API_BASE}/albums", include, params=params
                ),
            )

        return doc

    def ui_authenticate_flow(self) -> None:
        """Interactive first-time authentication (PKCE flow).

        1. Visit generated URL
        2. Paste full redirect URL (with ?code=...)
        3. Token auto-saved for future use
        """
        auth_url, _ = self.session.authorization_url(
            "https://login.tidal.com/authorize"
        )
        try:
            webbrowser.open(auth_url)
        except webbrowser.Error:
            ui.print_(f"Visit: {auth_url}")
        redirect_url = ui.input_("Paste redirected URL: ")
        self.session.fetch_token(
            "https://auth.tidal.com/v1/oauth2/token",
            authorization_response=redirect_url,
            include_client_id=True,
        )
        self.session.save_token(self.session.token)
        ui.print_(f"Saved tidal token in {self.session.token_path}")

    @staticmethod
    def merge_multiresource_pagination(
        a: Document[list[T]],
        b: Document[list[T]],
    ) -> Document[list[T]]:
        """
        Merge of b into a, following JSON:API spec rules.

        - Appends data arrays
        - Deduplicates included by (type, id)
        - Updates links (b overrides a)
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
            page_doc = self.get_json(
                url=next,
                params={**params, "include": include},
                **kwargs,
            )
            doc = self.merge_multiresource_pagination(doc, page_doc)

        # Dedupe include
        doc["included"] = list(
            {
                (item["type"], item["id"]): item
                for item in doc.get("included", [])
            }.values()
        )
        return doc
