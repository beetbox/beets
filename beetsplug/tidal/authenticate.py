from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import requests

from beets import ui

if TYPE_CHECKING:
    from pathlib import Path

    from beetsplug._typing import JSONDict


@dataclass(slots=True)
class TidalToken:
    """Serialized representation of tidal token"""

    access_token: str
    refresh_token: str
    scope: str
    user_id: int
    expires_at: datetime

    @classmethod
    def from_dict(cls, value: JSONDict) -> TidalToken:
        """Create token from API response dict (which has expires_in)."""
        if "expires_in" in value:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=value["expires_in"]
            )
        elif "expires_at" in value:
            if isinstance(value["expires_at"], str):
                expires_at = datetime.fromisoformat(value["expires_at"])
            else:
                expires_at = value["expires_at"]
        else:
            expires_at = datetime.now(timezone.utc)

        return cls(
            access_token=value["access_token"],
            refresh_token=value.get("refresh_token", ""),
            scope=value.get("scope", ""),
            user_id=int(value.get("user_id", 0)),
            expires_at=expires_at,
        )

    @classmethod
    def from_file(cls, file: str | Path) -> TidalToken:
        """Load token from JSON file."""
        with open(file) as f:
            data = json.load(f)
        return cls.from_dict(data)

    def update(self, value: JSONDict) -> None:
        """Update token with new data (e.g., from refresh)."""
        self.access_token = value["access_token"]
        if "refresh_token" in value:
            self.refresh_token = value["refresh_token"]
        if "scope" in value:
            self.scope = value["scope"]
        if "expires_in" in value:
            self.expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=value["expires_in"]
            )

    def to_dict(self) -> JSONDict:
        """Convert to dict for serialization."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "scope": self.scope,
            "user_id": self.user_id,
            "expires_at": self.expires_at.isoformat(),
        }

    def save_to(self, file: str | Path) -> None:
        """Save token to JSON file."""
        with open(file, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @property
    def is_expired(self):
        return datetime.now(tz=timezone.utc) >= self.expires_at

    def __call__(
        self, request: requests.PreparedRequest
    ) -> requests.PreparedRequest:
        request.headers["Authorization"] = f"Bearer {self.access_token}"
        return request


def ui_auth_flow(client_id: str) -> TidalToken:
    url, code_verifier, state = build_auth_url(
        client_id=client_id,
        redirect_uri="http://localhost",
        scope="search.read",
    )
    ui.print_(f"Visit: {url}")
    redirected_url = ui.input_("Paste redirected URL: ")
    verify_state(redirected_url, state)
    token_raw = request_token(
        redirected_url,
        code_verifier,
        client_id,
        "http://localhost",
    )
    return TidalToken.from_dict(token_raw)


def build_auth_url(
    client_id: str, redirect_uri: str, scope: str
) -> tuple[str | None, str, str]:
    """Build Tidal auth URL with PKCE. Returns (url, code_verifier, state)."""

    # pkce pair
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        )
        .decode()
        .rstrip("=")
    )
    state = secrets.token_urlsafe(8)
    req = requests.Request(
        "GET",
        "https://login.tidal.com/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "state": state,
        },
    )
    prepared = req.prepare()
    return prepared.url, code_verifier, state


def request_token(
    redirect_url: str,
    code_verifier: str,
    client_id: str,
    redirect_uri: str,
) -> JSONDict:
    """Exchange authorization code from redirect URL for a token."""

    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)

    try:
        code = params["code"][0]
    except (KeyError, IndexError):
        raise ValueError(f"No authorization code in URL: {redirect_url}")

    res = requests.post(
        "https://auth.tidal.com/v1/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
    )
    res.raise_for_status()
    return res.json()


def verify_state(redirect_url: str, expected_state: str) -> None:
    """Verify state parameter matches to prevent CSRF attacks."""
    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)

    try:
        received_state = params["state"][0]
    except (KeyError, IndexError):
        raise ValueError(f"No state parameter in URL: {redirect_url}")

    if received_state != expected_state:
        raise ValueError(
            f"State mismatch: expected {expected_state}, got {received_state}. "
            "Possible CSRF attack."
        )
