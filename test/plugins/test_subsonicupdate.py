"""Tests for the 'subsonicupdate' plugin."""

from __future__ import annotations

import re
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from beets import plugins
from beets.exceptions import UserError
from beets.test._common import item
from beets.test.helper import IOMixin, PluginTestHelper
from beetsplug.subsonicupdate import SubsonicUpdate

if TYPE_CHECKING:
    from requests_mock import Mocker

_p = pytest.param

START_SCAN_URL = "http://localhost:4040/rest/startScan"
SEARCH_URL = "http://localhost:4040/rest/search3"
STAR_URL = "http://localhost:4040/rest/star"
STARRED_URL = "http://localhost:4040/rest/getStarred2"

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

    @pytest.fixture(name="config")
    def helper_config(self, setup: None):
        """Reuse the helper's initialized config without resetting its paths."""
        return self.config

    @pytest.fixture(autouse=True)
    def subsonic(self, config) -> SubsonicUpdate:
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

    def test_config_preserves_library_directory(self, config):
        """The config fixture must preserve the helper's temporary paths."""
        assert config is self.config
        assert config["directory"].as_str() == str(self.lib_path)

    def test_start_scan(
        self,
        subsonic: SubsonicUpdate,
        requests_mock: Mocker,
        caplog: pytest.LogCaptureFixture,
    ):
        """Tests success path based on best case scenario."""
        requests_mock.get(START_SCAN_URL, text=SUCCESS_BODY)

        subsonic.start_scan(self.lib)

        assert requests_mock.call_count == 1
        assert requests_mock.request_history[0].qs["u"] == ["admin"]
        assert "Updating Subsonic; scanning 1000 tracks" in caplog.text

    def test_start_scan_failed_bad_credentials(
        self,
        subsonic: SubsonicUpdate,
        requests_mock: Mocker,
        caplog: pytest.LogCaptureFixture,
    ):
        """Tests failed path based on bad credentials."""
        requests_mock.get(START_SCAN_URL, text=FAILED_BODY)

        subsonic.start_scan(self.lib)

        assert "Wrong username or password." in caplog.text

    def test_start_scan_failed_not_found(
        self,
        subsonic: SubsonicUpdate,
        requests_mock: Mocker,
        caplog: pytest.LogCaptureFixture,
    ):
        """Tests failed path based on resource not found."""
        requests_mock.get(
            START_SCAN_URL, status_code=HTTPStatus.NOT_FOUND, text=ERROR_BODY
        )

        subsonic.start_scan(self.lib)

        assert "Not Found" in caplog.text

    def test_start_scan_failed_unreachable(
        self,
        subsonic: SubsonicUpdate,
        requests_mock: Mocker,
        caplog: pytest.LogCaptureFixture,
    ):
        """Tests failed path based on service not available."""
        requests_mock.get(
            START_SCAN_URL, exc=requests.exceptions.ConnectionError
        )

        subsonic.start_scan(self.lib)

        assert "Error connecting to Subsonic server" in caplog.text

    def test_url_with_context_path(
        self, config, subsonic: SubsonicUpdate, requests_mock: Mocker
    ):
        """Tests success for included with contextPath."""
        config["subsonic"]["url"] = "http://localhost:4040/contextPath/"
        requests_mock.get(
            "http://localhost:4040/contextPath/rest/startScan",
            text=SUCCESS_BODY,
        )

        subsonic.start_scan(self.lib)

        assert requests_mock.call_count == 1

    def test_url_with_trailing_forward_slash_url(
        self, config, subsonic: SubsonicUpdate, requests_mock: Mocker
    ):
        """Tests success path based on trailing forward slash."""
        config["subsonic"]["url"] = "http://localhost:4040/"
        requests_mock.get(START_SCAN_URL, text=SUCCESS_BODY)

        subsonic.start_scan(self.lib)

        assert requests_mock.call_count == 1

    def test_url_with_missing_port(
        self, config, subsonic: SubsonicUpdate, requests_mock: Mocker
    ):
        """Tests success path based on missing port."""
        config["subsonic"]["url"] = "http://localhost/airsonic"
        requests_mock.get(
            "http://localhost/airsonic/rest/startScan", text=SUCCESS_BODY
        )

        subsonic.start_scan(self.lib)

        assert requests_mock.call_count == 1

    def test_url_with_missing_scheme(
        self,
        config,
        subsonic: SubsonicUpdate,
        requests_mock: Mocker,
        caplog: pytest.LogCaptureFixture,
    ):
        """Reject a URL without a scheme before sending any HTTP request."""
        config["subsonic"]["url"] = "localhost/airsonic"

        subsonic.start_scan(self.lib)

        assert "Error connecting to Subsonic server" in caplog.text
        assert "No scheme supplied" in caplog.text
        assert requests_mock.call_count == 0

    def test_start_scan_failed_non_json_response(
        self,
        subsonic: SubsonicUpdate,
        requests_mock: Mocker,
        caplog: pytest.LogCaptureFixture,
    ):
        """Tests failed path based on a non-JSON server response."""
        requests_mock.get(
            START_SCAN_URL,
            text="<html>server unavailable</html>",
            headers={"Content-Type": "text/html"},
        )

        subsonic.start_scan(self.lib)

        assert "Subsonic server returned a non-JSON response" in caplog.text

    @pytest.mark.parametrize(
        "body", ["null", "[]", '{"subsonic-response": null}']
    )
    def test_start_scan_failed_invalid_response(
        self,
        subsonic: SubsonicUpdate,
        requests_mock: Mocker,
        caplog: pytest.LogCaptureFixture,
        body: str,
    ):
        """Valid JSON of an unexpected shape is reported, not raised."""
        requests_mock.get(START_SCAN_URL, text=body)

        subsonic.start_scan(self.lib)

        assert "Subsonic server returned an invalid response" in caplog.text

    @pytest.mark.parametrize(
        "scan_status, message",
        [
            (None, "Updating Subsonic; scanning 0 tracks"),
            ("oops", "Subsonic server returned an invalid 'scanStatus'"),
        ],
    )
    def test_start_scan_handles_malformed_scan_status(
        self,
        subsonic: SubsonicUpdate,
        requests_mock: Mocker,
        caplog: pytest.LogCaptureFixture,
        scan_status,
        message,
    ):
        requests_mock.get(START_SCAN_URL, json=_ok(scanStatus=scan_status))

        subsonic.start_scan(self.lib)

        assert message in caplog.text

    def test_cli_command_starts_scan(self, requests_mock: Mocker):
        """The `subsonicupdate` command triggers a scan."""
        requests_mock.get(START_SCAN_URL, text=SUCCESS_BODY)

        self.run_command("subsonicupdate")

        assert requests_mock.call_count == 1

    def test_cli_command_rejects_arguments(self, requests_mock: Mocker):
        """The command rejects stray arguments without starting a scan."""
        requests_mock.get(START_SCAN_URL, text=SUCCESS_BODY)

        with pytest.raises(UserError, match="does not take arguments"):
            self.run_command("subsonicupdate", "startScan")

        assert requests_mock.call_count == 0

    def test_cli_command_starts_scan_when_auto_disabled(
        self, config, requests_mock: Mocker
    ):
        """The `subsonicupdate` command works without `auto` enabled."""
        config["subsonic"]["auto"] = False
        self.reload_plugin()
        requests_mock.get(START_SCAN_URL, text=SUCCESS_BODY)

        self.run_command("subsonicupdate")

        assert requests_mock.call_count == 1

    def test_database_change_starts_scan_on_exit(self, requests_mock: Mocker):
        """A library change triggers a scan when the command exits."""
        requests_mock.get(START_SCAN_URL, text=SUCCESS_BODY)

        plugins.send("database_change", lib=self.lib, model=item())
        assert requests_mock.call_count == 0
        plugins.send("cli_exit", lib=self.lib)

        assert requests_mock.call_count == 1

    def test_smartplaylist_update_starts_scan_on_exit(
        self, requests_mock: Mocker
    ):
        """A smart playlist update triggers a scan when the command exits."""
        requests_mock.get(START_SCAN_URL, text=SUCCESS_BODY)

        plugins.send("smartplaylist_update")
        assert requests_mock.call_count == 0
        plugins.send("cli_exit", lib=self.lib)

        assert requests_mock.call_count == 1

    def test_no_scan_on_exit_without_changes(self, requests_mock: Mocker):
        """Read-only commands do not trigger a scan."""
        requests_mock.get(START_SCAN_URL, text=SUCCESS_BODY)

        plugins.send("cli_exit", lib=self.lib)

        assert requests_mock.call_count == 0

    def test_auto_disabled_does_not_start_scan(
        self, config, requests_mock: Mocker
    ):
        """With `auto` disabled no scan is requested on library changes."""
        config["subsonic"]["auto"] = False
        self.reload_plugin()
        requests_mock.get(START_SCAN_URL, text=SUCCESS_BODY)

        plugins.send("database_change", lib=self.lib, model=item())
        plugins.send("smartplaylist_update")
        plugins.send("cli_exit", lib=self.lib)

        assert requests_mock.call_count == 0


def _params(url):
    """Get the query parameters from a URL, preserving their case."""
    return parse_qs(urlparse(url).query)


def _ok(**payload):
    return {"subsonic-response": {"status": "ok", **payload}}


def _songs(*songs):
    return _ok(searchResult3={"song": list(songs)})


SONG = {"id": "song-1", "artist": "Artist", "album": "Album", "title": "Song"}


class TestSetFavorite(IOMixin, PluginTestHelper):
    plugin = "subsonicupdate"
    preload_plugin = False

    @pytest.fixture(autouse=True)
    def subsonic(self, setup: None, requests_mock: Mocker):
        """Load the plugin against a fake server that remembers starred songs."""
        self.starred: set[str] = set()

        def star(request, _):
            self.starred.update(_params(request.url)["id"])
            return _ok()

        def starred(*_):
            return _ok(starred2={"song": [{"id": i} for i in self.starred]})

        requests_mock.get(STAR_URL, json=star)
        requests_mock.get(STARRED_URL, json=starred)
        self.config["subsonic"].set(
            {
                "user": "admin",
                "pass": "secret",
                "url": "http://localhost:4040",
                "auto": False,
            }
        )
        self.load_plugins()

    def test_uses_stored_subsonic_id(self, requests_mock: Mocker):
        item = self.add_item(title="Song", subsonic_id="song-1")

        self.run_command("subsonic-set-favorite", f"id:{item.id}")

        _, star, _ = requests_mock.request_history
        params = _params(star.url)
        assert params["id"] == ["song-1"]
        assert params["u"] == ["admin"]
        assert params["f"] == ["json"]
        assert "t" in params
        assert "s" in params

    def test_searches_server_and_stores_id_when_missing(
        self, requests_mock: Mocker
    ):
        item = self.add_item(artist="Artist", album="Album", title="Song")
        requests_mock.get(SEARCH_URL, json=_songs(SONG))

        self.run_command("subsonic-set-favorite", f"id:{item.id}")

        _, search, star, _ = requests_mock.request_history
        assert _params(search.url)["query"] == ["Artist Album Song"]
        assert _params(star.url)["id"] == ["song-1"]
        item.load()
        assert item.subsonic_id == "song-1"

    def test_reports_progress_every_tenth_of_tracks(
        self, caplog: pytest.LogCaptureFixture
    ):
        for i in range(25):
            self.add_item(title=f"Song {i}", subsonic_id=f"song-{i}")

        with caplog.at_level("INFO"):
            self.run_command("subsonic-set-favorite", "subsonic_id:song")

        messages = [r.getMessage() for r in caplog.records]
        progress = [m for m in messages if m.startswith("Processed")]
        counts = [*range(2, 25, 2), 25]
        assert progress == [f"Processed {n}/25 tracks" for n in counts]

    def test_retries_with_folded_unicode_query(self, requests_mock: Mocker):
        item = self.add_item(
            artist="Von Bikräv", album="Album", title="Éternité"
        )
        song = {**SONG, "artist": "Von Bikrav", "title": "Eternite"}
        empty = {"json": _ok(searchResult3={})}
        requests_mock.get(
            SEARCH_URL, [empty, empty, empty, empty, {"json": _songs(song)}]
        )

        self.run_command("subsonic-set-favorite", f"id:{item.id}")

        *_, folded, star, _ = requests_mock.request_history
        assert _params(folded.url)["query"] == ["von bikrav album eternite"]
        assert _params(star.url)["id"] == ["song-1"]

    @pytest.mark.parametrize(
        "songs, message, expected_calls",
        [
            _p([], "No Subsonic match", 5, id="no match"),
            _p([{**SONG, "title": "Songbird"}], "No Subsonic match", 5, id="partial word"),
            _p([{**SONG, "title": "Song (Live Performance)"}], "No Subsonic match", 5, id="other version"),
            _p([{"id": "song-1", "title": "Song"}], "No Subsonic match", 5, id="missing fields"),
            _p([SONG, {**SONG, "id": "song-2"}], "Skipping ambiguous match", 2, id="ambiguous"),
        ],
    )  # fmt: skip
    def test_skips_unresolvable_matches(
        self,
        requests_mock: Mocker,
        caplog: pytest.LogCaptureFixture,
        songs,
        message,
        expected_calls,
    ):
        item = self.add_item(artist="Artist", album="Album", title="Song")
        requests_mock.get(SEARCH_URL, json=_songs(*songs))

        with caplog.at_level("WARNING"):
            self.run_command("subsonic-set-favorite", f"id:{item.id}")

        assert requests_mock.call_count == expected_calls
        assert message in caplog.text

    def test_does_not_match_unrelated_song_for_non_latin_metadata(
        self, requests_mock: Mocker, caplog: pytest.LogCaptureFixture
    ):
        item = self.add_item(
            artist="Кино", album="Альбом", title="Группа крови"
        )
        requests_mock.get(SEARCH_URL, json=_songs(SONG))

        with caplog.at_level("WARNING"):
            self.run_command("subsonic-set-favorite", f"id:{item.id}")

        assert not any(
            r.url.startswith(STAR_URL) for r in requests_mock.request_history
        )
        assert "No Subsonic match" in caplog.text

    def test_stars_and_reports_only_new_favourites(self, requests_mock: Mocker):
        self.starred.add("song-1")
        self.add_item(artist="A", album="B", title="Song", subsonic_id="song-1")
        self.add_item(artist="A", album="B", title="New", subsonic_id="song-2")
        self.add_item(artist="A", album="B", title="Dupe", subsonic_id="song-2")

        output = self.run_with_output(
            "subsonic-set-favorite", "subsonic_id:song"
        )

        *_, star, _ = requests_mock.request_history
        assert _params(star.url)["id"] == ["song-2"]
        assert output.splitlines() == [
            "A - B - New",
            "Marked 1 new tracks as Subsonic favourites.",
        ]

    def test_stars_songs_in_chunks(self, requests_mock: Mocker):
        for i in range(101):
            self.add_item(title=f"Song {i}", subsonic_id=f"song-{i}")

        self.run_command("subsonic-set-favorite", "subsonic_id:song")

        _, *stars, _ = requests_mock.request_history
        assert [len(_params(s.url)["id"]) for s in stars] == [100, 1]

    def test_researches_stale_subsonic_id(
        self, requests_mock: Mocker, caplog: pytest.LogCaptureFixture
    ):
        def star(request, _):
            # Like Navidrome, skip unknown IDs and still report success
            self.starred.update(set(_params(request.url)["id"]) - {"gone"})
            return _ok()

        requests_mock.get(STAR_URL, json=star)
        requests_mock.get(SEARCH_URL, json=_songs(SONG))
        item = self.add_item(
            artist="Artist", album="Album", title="Song", subsonic_id="gone"
        )

        with caplog.at_level("WARNING"):
            output = self.run_with_output(
                "subsonic-set-favorite", f"id:{item.id}"
            )

        item.load()
        assert item.subsonic_id == "song-1"
        assert self.starred == {"song-1"}
        assert "searching for it again" in caplog.text
        assert "Marked 1 new tracks as Subsonic favourites." in output

    def test_reports_server_errors(self, requests_mock: Mocker):
        item = self.add_item(title="Song", subsonic_id="song-1")
        requests_mock.get(STAR_URL, text=FAILED_BODY)

        with pytest.raises(UserError, match="Wrong username or password"):
            self.run_command("subsonic-set-favorite", f"id:{item.id}")

    @pytest.mark.parametrize("auth", ["token", "password"])
    def test_hides_credentials_in_http_errors(
        self, requests_mock: Mocker, auth: str
    ):
        self.config["subsonic"]["auth"] = auth
        item = self.add_item(title="Song", subsonic_id="song-1")
        requests_mock.get(STAR_URL, status_code=HTTPStatus.UNAUTHORIZED)

        with pytest.raises(UserError, match="401") as exc_info:
            self.run_command("subsonic-set-favorite", f"id:{item.id}")

        assert not re.search(r"[?&][pts]=[^*]", str(exc_info.value))

    @pytest.mark.parametrize("answer, expected_calls", [("y", 3), ("n", 0)])
    def test_confirms_before_favouriting_whole_library(
        self, requests_mock: Mocker, answer, expected_calls
    ):
        self.add_item(title="Song", subsonic_id="song-1")
        self.io.addinput(answer)

        output = self.run_with_output("subsonic-set-favorite")

        assert "Mark all 1 tracks as Subsonic favourites" in output
        assert requests_mock.call_count == expected_calls
