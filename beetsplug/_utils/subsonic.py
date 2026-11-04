"""Client for servers implementing the Subsonic API."""

from __future__ import annotations

import hashlib
import re
import secrets
import string
from binascii import hexlify
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import requests

from beets.util import chunks

from .requests import RequestHandler

if TYPE_CHECKING:
    from collections.abc import Iterable

    from beetsplug._typing import JSONDict

# Song IDs are sent as query parameters, so keep URLs well below the usual
# 8 KB limit of servers and reverse proxies.
STAR_CHUNK_SIZE = 100

# Query parameters carrying the password, or the token and salt derived from it
SECRET_PARAM_PAT = re.compile(r"([?&][pts]=)[^&\s]+")


class SubsonicError(Exception):
    """Raised when the server rejects or cannot complete an API request."""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


@dataclass
class SubsonicClient(RequestHandler):
    """Authenticated client for the Subsonic REST API."""

    base_url: str
    username: str
    password: str
    auth: str

    def _url(self, endpoint: str) -> str:
        return f"{self.base_url.rstrip('/')}/rest/{endpoint}"

    def _auth_params(self) -> dict[str, str]:
        # Token auth needs API 1.13.0 (Subsonic 5.3), older servers only
        # support sending the hex-encoded password.
        if self.auth == "token":
            alphabet = string.ascii_letters + string.digits
            salt = "".join(secrets.choice(alphabet) for _ in range(12))
            token = hashlib.md5(f"{self.password}{salt}".encode()).hexdigest()
            return {"t": token, "s": salt, "v": "1.13.0"}
        if self.auth == "password":
            encoded = hexlify(self.password.encode()).decode()
            return {"p": f"enc:{encoded}", "v": "1.12.0"}

        raise SubsonicError("auth must be either 'token' or 'password'")

    def _request(self, endpoint: str, params: dict[str, Any]) -> JSONDict:
        params = {
            "u": self.username,
            "c": "beets",
            "f": "json",
            **self._auth_params(),
            **params,
        }
        # JSONDecodeError is a RequestException too, so handle it first
        try:
            data = self.get_json(self._url(endpoint), params=params)
        except requests.exceptions.JSONDecodeError as exc:
            raise SubsonicError(
                "Subsonic server returned a non-JSON response"
            ) from exc
        except requests.exceptions.RequestException as exc:
            # Error messages may include the request URL with credentials
            message = SECRET_PARAM_PAT.sub(r"\1***", str(exc))
            raise SubsonicError(
                f"Error connecting to Subsonic server: {message}"
            ) from exc

        response = data.get("subsonic-response", {})
        status = response.get("status")
        if status == "failed":
            error = response.get("error", {})
            raise SubsonicError(error.get("message", "unknown Subsonic error"))
        if status != "ok":
            raise SubsonicError("Subsonic server returned an invalid response")
        return response

    def start_scan(self) -> int:
        """Start a library scan and return the number of tracks found so far."""
        response = self._request("startScan", {})
        return response.get("scanStatus", {}).get("count", 0)

    def search_songs(self, query: str, count: int) -> list[JSONDict]:
        """Find songs using the tag-based search."""
        response = self._request(
            "search3",
            {
                "query": query,
                "artistCount": 0,
                "albumCount": 0,
                "songCount": count,
            },
        )
        return _as_list(response.get("searchResult3", {}).get("song"))

    def starred_song_ids(self) -> set[str]:
        """Return IDs of songs the authenticated user has already starred."""
        response = self._request("getStarred2", {})
        songs = _as_list(response.get("starred2", {}).get("song"))
        return {str(song["id"]) for song in songs}

    def star_songs(self, song_ids: Iterable[str]) -> None:
        """Mark songs as favourites for the authenticated user."""
        for ids in chunks(list(song_ids), STAR_CHUNK_SIZE):
            self._request("star", {"id": ids})
