"""Tests for the 'subsonicplaylist' plugin."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import pytest

from beets import plugins
from beets.test.helper import PluginTestHelper
from beetsplug.subsonicplaylist import SubsonicPlaylistPlugin

if TYPE_CHECKING:
    from requests_mock import Mocker

BASE_URL = "http://localhost:4040"

# Server-provided error messages can contain braces; they must be logged
# verbatim instead of being treated as a format string.
ERROR_BODY = """<?xml version="1.0" encoding="UTF-8"?>
<subsonic-response status="failed" version="1.16.1">
    <error code="70" message="Playlist not found: {id}"/>
</subsonic-response>
"""


class TestSubsonicPlaylist(PluginTestHelper):
    plugin = "subsonicplaylist"
    preload_plugin = False

    @pytest.fixture(autouse=True)
    def subsonicplaylist(self, setup: None) -> SubsonicPlaylistPlugin:
        self.config["subsonicplaylist"].set(
            {"base_url": BASE_URL, "username": "admin", "password": "admin"}
        )
        self.load_plugins()
        return next(
            plugin
            for plugin in plugins.find_plugins()
            if isinstance(plugin, SubsonicPlaylistPlugin)
        )

    def test_get_playlist_error_message_is_logged_verbatim(
        self,
        subsonicplaylist: SubsonicPlaylistPlugin,
        requests_mock: Mocker,
        caplog: pytest.LogCaptureFixture,
    ):
        requests_mock.get(f"{BASE_URL}/rest/getPlaylist", text=ERROR_BODY)

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            result = subsonicplaylist.get_playlist("1")

        assert result is None
        assert "Playlist not found: {id}" in caplog.text
