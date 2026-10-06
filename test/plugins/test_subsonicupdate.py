"""Tests for the 'subsonicupdate' plugin."""

from __future__ import annotations

import pytest
import responses

from beets import config, plugins
from beets.test._common import item
from beets.test.helper import PluginTestHelper
from beetsplug.subsonicupdate import SubsonicUpdate

START_SCAN_URL = "http://localhost:4040/rest/startScan"

SUCCESS_BODY = """
{
    "subsonic-response": {
        "status": "ok",
        "version": "1.15.0",
        "scanStatus": {
            "scanning": true,
            "count": 1000
        }
    }
}
"""

FAILED_BODY = """
{
    "subsonic-response": {
        "status": "failed",
        "version": "1.15.0",
        "error": {
            "code": 40,
            "message": "Wrong username or password."
        }
    }
}
"""

ERROR_BODY = """
{
    "timestamp": 1599185854498,
    "status": 404,
    "error": "Not Found",
    "message": "No message available",
    "path": "/rest/startScn"
}
"""


class TestSubsonicUpdate(PluginTestHelper):
    """Test class for subsonicupdate."""

    plugin = "subsonicupdate"
    preload_plugin = False

    @pytest.fixture(autouse=True)
    def subsonic(self, setup: None) -> SubsonicUpdate:
        """Load the plugin with a reachable Subsonic server configuration."""
        config["subsonic"].set(
            {"user": "admin", "pass": "admin", "url": "http://localhost:4040"}
        )
        return self.reload_plugin()

    def reload_plugin(self) -> SubsonicUpdate:
        """(Re)load the plugin so it picks up the current configuration."""
        self.unload_plugins()
        self.load_plugins()
        return next(
            plugin
            for plugin in plugins.find_plugins()
            if isinstance(plugin, SubsonicUpdate)
        )

    @responses.activate
    def test_start_scan(self, subsonic: SubsonicUpdate):
        """Tests success path based on best case scenario."""
        responses.add(
            responses.GET, START_SCAN_URL, status=200, body=SUCCESS_BODY
        )

        subsonic.start_scan(self.lib)

        assert len(responses.calls) == 1

    @responses.activate
    def test_start_scan_failed_bad_credentials(
        self, subsonic: SubsonicUpdate, caplog: pytest.LogCaptureFixture
    ):
        """Tests failed path based on bad credentials."""
        responses.add(
            responses.GET, START_SCAN_URL, status=200, body=FAILED_BODY
        )

        subsonic.start_scan(self.lib)

        assert "Wrong username or password." in caplog.text

    @responses.activate
    def test_start_scan_failed_not_found(self, subsonic: SubsonicUpdate):
        """Tests failed path based on resource not found."""
        responses.add(
            responses.GET, START_SCAN_URL, status=404, body=ERROR_BODY
        )

        subsonic.start_scan(self.lib)

    def test_start_scan_failed_unreachable(self, subsonic: SubsonicUpdate):
        """Tests failed path based on service not available."""
        subsonic.start_scan(self.lib)

    @responses.activate
    def test_url_with_context_path(self, subsonic: SubsonicUpdate):
        """Tests success for included with contextPath."""
        config["subsonic"]["url"] = "http://localhost:4040/contextPath/"
        responses.add(
            responses.GET,
            "http://localhost:4040/contextPath/rest/startScan",
            status=200,
            body=SUCCESS_BODY,
        )

        subsonic.start_scan(self.lib)

        assert len(responses.calls) == 1

    @responses.activate
    def test_url_with_trailing_forward_slash_url(
        self, subsonic: SubsonicUpdate
    ):
        """Tests success path based on trailing forward slash."""
        config["subsonic"]["url"] = "http://localhost:4040/"
        responses.add(
            responses.GET, START_SCAN_URL, status=200, body=SUCCESS_BODY
        )

        subsonic.start_scan(self.lib)

        assert len(responses.calls) == 1

    @responses.activate
    def test_url_with_missing_port(self, subsonic: SubsonicUpdate):
        """Tests failed path based on missing port."""
        config["subsonic"]["url"] = "http://localhost/airsonic"
        responses.add(
            responses.GET,
            "http://localhost/airsonic/rest/startScan",
            status=200,
            body=SUCCESS_BODY,
        )

        subsonic.start_scan(self.lib)

        assert len(responses.calls) == 1

    @responses.activate
    def test_url_with_missing_schema(self, subsonic: SubsonicUpdate):
        """Tests failed path based on missing schema."""
        config["subsonic"]["url"] = "localhost:4040/airsonic"
        responses.add(
            responses.GET, START_SCAN_URL, status=200, body=SUCCESS_BODY
        )

        subsonic.start_scan(self.lib)

    @responses.activate
    def test_start_scan_failed_non_json_response(
        self, subsonic: SubsonicUpdate, caplog: pytest.LogCaptureFixture
    ):
        """Tests failed path based on a non-JSON server response."""
        responses.add(
            responses.GET,
            START_SCAN_URL,
            status=503,
            body="<html>server unavailable</html>",
            content_type="text/html",
        )

        subsonic.start_scan(self.lib)

        assert "Subsonic server returned a non-JSON response" in caplog.text

    @responses.activate
    def test_cli_command_starts_scan(self):
        """The `subsonicupdate` command triggers a scan."""
        responses.add(
            responses.GET, START_SCAN_URL, status=200, body=SUCCESS_BODY
        )

        self.run_command("subsonicupdate")

        assert len(responses.calls) == 1

    @responses.activate
    def test_cli_command_starts_scan_when_auto_disabled(self):
        """The `subsonicupdate` command works without `auto` enabled."""
        config["subsonic"]["auto"] = False
        self.reload_plugin()
        responses.add(
            responses.GET, START_SCAN_URL, status=200, body=SUCCESS_BODY
        )

        self.run_command("subsonicupdate")

        assert len(responses.calls) == 1

    @responses.activate
    def test_database_change_starts_scan_on_exit(self):
        """A library change triggers a scan when the command exits."""
        responses.add(
            responses.GET, START_SCAN_URL, status=200, body=SUCCESS_BODY
        )

        plugins.send("database_change", lib=self.lib, model=item())
        assert not responses.calls
        plugins.send("cli_exit", lib=self.lib)

        assert len(responses.calls) == 1

    @responses.activate
    def test_smartplaylist_update_starts_scan_on_exit(self):
        """A smart playlist update triggers a scan when the command exits."""
        responses.add(
            responses.GET, START_SCAN_URL, status=200, body=SUCCESS_BODY
        )

        plugins.send("smartplaylist_update")
        assert not responses.calls
        plugins.send("cli_exit", lib=self.lib)

        assert len(responses.calls) == 1

    @responses.activate
    def test_no_scan_on_exit_without_changes(self):
        """Read-only commands do not trigger a scan."""
        responses.add(
            responses.GET, START_SCAN_URL, status=200, body=SUCCESS_BODY
        )

        plugins.send("cli_exit", lib=self.lib)

        assert not responses.calls

    @responses.activate
    def test_auto_disabled_does_not_start_scan(self):
        """With `auto` disabled no scan is requested on library changes."""
        config["subsonic"]["auto"] = False
        self.reload_plugin()
        responses.add(
            responses.GET, START_SCAN_URL, status=200, body=SUCCESS_BODY
        )

        plugins.send("database_change", lib=self.lib, model=item())
        plugins.send("smartplaylist_update")
        plugins.send("cli_exit", lib=self.lib)

        assert not responses.calls
