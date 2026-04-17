from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING

import requests
from requests_oauthlib import OAuth2Session
from urllib3.util.retry import Retry

from beets.logging import getLogger
from beetsplug._utils.requests import RateLimitAdapter, TimeoutAndRetrySession

if TYPE_CHECKING:
    from beetsplug._typing import JSONDict

API_BASE = "https://openapi.tidal.com/v2"

log = getLogger("beets.tidal")


class TidalSession(OAuth2Session, TimeoutAndRetrySession):
    """Tidal API session with automatic OAuth2 PKCE authentication.

    Handles:
    - Initial interactive PKCE flow (Tidal required)
    - Automatic token refresh
    - Rate limiting (~4 req/s)
    - Token persistence
    - API base URL prefixing
    """

    token_path: Path

    def __init__(self, client_id: str, token_path: str | Path) -> None:
        self.token_path = Path(token_path)

        # Load token & init parent
        token = self.load_token()
        super().__init__(
            client_id,
            token=token,
            scope="search.read",
            auto_refresh_url="https://auth.tidal.com/v1/oauth2/token",
            redirect_uri="https://localhost",
            auto_refresh_kwargs={"client_id": client_id},
            token_updater=self.save_token,
            pkce="S256",
        )

        # Retry on server errors
        retry = Retry(
            total=6,
            backoff_factor=0.5,
            status_forcelist=[
                HTTPStatus.INTERNAL_SERVER_ERROR,
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
            ],
        )
        # Rate limit to ~4/s as tidal will penalize heavily if not respected
        adapter = RateLimitAdapter(rate_limit=0.25, max_retries=retry)
        self.mount("https://auth.tidal.com/", adapter)
        self.mount(API_BASE, adapter)

    def load_token(self) -> JSONDict | None:
        """Load token from JSON file."""
        if self.token_path.exists():
            with open(self.token_path) as f:
                return json.load(f)
        return None

    def save_token(self, token: JSONDict) -> None:
        """Save token to JSON file."""
        with open(self.token_path, "w") as f:
            json.dump(token, f, indent=2)

    def request(
        self, method: str | bytes, url: str | bytes, *args, **kwargs
    ) -> requests.Response:
        """Override for Tidal-specific base URL and rate limits."""
        if isinstance(url, str) and not url.startswith("http"):
            url = API_BASE + url

        try:
            res = super().request(method, url, *args, **kwargs)
        except requests.exceptions.HTTPError as e:
            res = e.response
            if res.status_code == 429:
                self._handle_rate_limit(res)
                return self.request(method, url, *args, **kwargs)
            raise
        return res

    def _handle_rate_limit(self, response: requests.Response) -> None:
        remaining = int(response.headers.get("Retry-After", 0))
        if remaining > 0:
            log.debug(
                "Rate limit exceeded. Retrying after {0} seconds.", remaining
            )
            sleep(remaining)
        else:
            raise Exception(
                "Rate limit handling failed: Retry-After header is missing or invalid"
            )
        return
