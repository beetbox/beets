"""Tests for the 'plexupdate' plugin."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from beets.exceptions import UserError
from beetsplug._utils.requests import SingletonMeta
from beetsplug.plexupdate import (
    PLEX_API,
    PlexAPI,
    PlexSession,
    UnauthorizedPlexError,
)

if TYPE_CHECKING:
    from pathlib import Path

    from requests_mock import Mocker


@pytest.fixture(autouse=True)
def reset_plex_session():
    """Drop the PlexSession singleton so each test gets a fresh session."""
    yield
    SingletonMeta._instances.pop(PlexSession, None)


@pytest.fixture
def api(tmp_path: Path) -> PlexAPI:
    """PlexAPI for the local test server with a per-test token file."""
    return PlexAPI(
        token_path=tmp_path / "plex_token.json",
        host="localhost",
        port=32400,
        library_name="Music",
        secure=False,
        verify=True,
        token_override="",
    )


@pytest.fixture
def session(tmp_path: Path) -> PlexSession:
    """PlexSession bound to a token file in a per-test directory."""
    return PlexSession(token_path=tmp_path / "plex_token.json")


@pytest.fixture
def plex_tv(requests_mock: Mocker) -> Mocker:
    """Mock the plex.tv PIN flow: issuing a pin and still-pending polls."""
    requests_mock.post(
        f"{PLEX_API}/pins", json={"id": 1, "code": "ABCD", "expiresIn": 1800}
    )
    requests_mock.get(f"{PLEX_API}/pins/1", json={"id": 1, "code": "ABCD"})
    return requests_mock


class TestUpdateLibrary:
    def test_get_named_music_section(self, requests_mock, api):
        requests_mock.get(
            "http://localhost:32400/library/sections",
            json={
                "MediaContainer": {
                    "Directory": [
                        {"key": "3", "title": "Movies"},
                        {"key": "2", "title": "My Music Library"},
                    ]
                }
            },
        )
        api.library_name = "My Music Library"

        assert api.get_music_section() == "2"

    def test_update_library(self, requests_mock, api):
        requests_mock.get(
            "http://localhost:32400/library/sections",
            json={
                "MediaContainer": {
                    "Directory": [{"key": "2", "title": "Music"}]
                }
            },
        )
        requests_mock.get("http://localhost:32400/library/sections/2/refresh")

        assert api.update_library().status_code == 200

    def test_update_library_unauthorized(self, requests_mock, api):
        """A rejected token surfaces as an UnauthorizedPlexError."""
        requests_mock.get(
            "http://localhost:32400/library/sections",
            json={
                "MediaContainer": {
                    "Directory": [{"key": "2", "title": "Music"}]
                }
            },
        )
        requests_mock.get(
            "http://localhost:32400/library/sections/2/refresh", status_code=401
        )

        with pytest.raises(UnauthorizedPlexError, match="reauthenticate"):
            api.update_library()

    def test_update_library_missing_section(self, requests_mock, api):
        # The server has no section with the configured name.
        requests_mock.get(
            "http://localhost:32400/library/sections",
            json={
                "MediaContainer": {
                    "Directory": [{"key": "3", "title": "Other Library"}]
                }
            },
        )

        with pytest.raises(UserError, match="No music library named"):
            api.update_library()


class TestPlexSession:
    def test_session_saves_token(self, session):
        session.save_token({"X-Plex-Token": "TOKEN123"})

        assert session.token == "TOKEN123"
        assert session.load_token() == {
            "X-Plex-Token": "TOKEN123",
            "client_identifier": session.client_id,
        }

    def test_wait_for_login_timeout(self, plex_tv, session):
        # The pin never gets an auth token.
        with mock.patch("beetsplug.plexupdate.time.sleep"):
            assert session.wait_for_login(1, timeout=1) is None

    def test_request_attaches_token_to_local_server(
        self, requests_mock, session
    ):
        """The stored token is sent to the local server."""
        requests_mock.get("http://localhost:32400/library/sections", json={})
        session.save_token({"X-Plex-Token": "TOKEN123"})

        session.get("http://localhost:32400/library/sections")

        assert (
            requests_mock.request_history[0].headers["X-Plex-Token"]
            == "TOKEN123"
        )

    def test_request_prefers_configured_token(self, requests_mock, tmp_path):
        """The configured token wins over the stored plex.tv token."""
        session = PlexSession(
            token_path=tmp_path / "plex_token.json",
            token_override="CONFIG_TOKEN",
        )
        session.save_token({"X-Plex-Token": "TOKEN123"})
        requests_mock.get("http://localhost:32400/library/sections", json={})

        session.get("http://localhost:32400/library/sections")

        assert (
            requests_mock.request_history[0].headers["X-Plex-Token"]
            == "CONFIG_TOKEN"
        )


class TestUIAuthenticateFlow:
    def test_ui_authenticate_flow(self, requests_mock, plex_tv, api):
        # The first poll is still pending, the second grants access.
        requests_mock.get(
            f"{PLEX_API}/pins/1",
            response_list=[
                {"json": {"id": 1, "code": "ABCD"}},
                {"json": {"id": 1, "code": "ABCD", "authToken": "TOKEN123"}},
            ],
        )

        with (
            mock.patch("beetsplug.plexupdate.time.sleep"),
            mock.patch("beetsplug.plexupdate.webbrowser.open") as open_mock,
        ):
            api.ui_authenticate_flow()

        open_mock.assert_called_once()

        # The pin request carries the identifying headers.
        request = requests_mock.request_history[0]
        assert (
            request.headers["X-Plex-Client-Identifier"] == api.session.client_id
        )

        # The access token is persisted for later runs.
        assert api.session.token == "TOKEN123"
        assert json.loads(
            api.session.token_path.read_text(encoding="utf-8")
        ) == {
            "X-Plex-Token": "TOKEN123",
            "client_identifier": api.session.client_id,
        }

    def test_ui_authenticate_flow_timeout(self, plex_tv, api):
        with (
            mock.patch("beetsplug.plexupdate.time.sleep"),
            mock.patch("beetsplug.plexupdate.webbrowser.open"),
            mock.patch.object(api.session, "wait_for_login", return_value=None),
        ):
            with pytest.raises(UserError):
                api.ui_authenticate_flow()

        # No token is stored when the login is not completed.
        assert api.session.token is None

    def test_ui_authenticate_flow_network_error(self, requests_mock, api):
        # A failing plex.tv request surfaces as a UserError instead of a
        # raw requests exception.
        requests_mock.post(f"{PLEX_API}/pins", status_code=500)

        with pytest.raises(UserError, match="Plex login flow failed"):
            api.ui_authenticate_flow()
