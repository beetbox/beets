from typing import Any, ClassVar
from unittest.mock import ANY, Mock, call, patch

from beets import util
from beets.library import Item
from beets.test.helper import PluginTestHelper
from beetsplug.mpdstats import MPDStats, mpd_config


class TestMPDStats(PluginTestHelper):
    plugin = "mpdstats"

    def test_update_rating(self):
        item = Item(title="title", path="", id=1)
        item.add(self.lib)

        log = Mock()
        mpdstats = MPDStats(self.lib, log)

        assert not mpdstats.update_rating(item, True)
        assert not mpdstats.update_rating(None, True)

    def test_get_item(self):
        item_path = util.normpath("/foo/bar.flac")
        item = Item(title="title", path=item_path, id=1)
        item.add(self.lib)

        log = Mock()
        mpdstats = MPDStats(self.lib, log)

        assert str(mpdstats.get_item(item_path)) == str(item)
        assert mpdstats.get_item("/some/non-existing/path") is None
        assert "item not found:" in log.info.call_args[0][0]

    STATUSES: ClassVar[list[dict[str, Any]]] = [
        {"state": "some-unknown-one"},
        {"state": "pause"},
        {"state": "play", "songid": 1, "time": "0:1"},
        {"state": "stop"},
    ]
    EVENTS = [["player"]] * (len(STATUSES) - 1) + [KeyboardInterrupt]
    item_path = util.normpath("/foo/bar.flac")
    songid = 1

    @patch(
        "beetsplug.mpdstats.MPDClientWrapper",
        return_value=Mock(
            **{
                "events.side_effect": EVENTS,
                "status.side_effect": STATUSES,
                "currentsong.return_value": (item_path, songid),
            }
        ),
    )
    def test_run_mpdstats(self, mpd_mock):
        item = Item(title="title", path=self.item_path, id=1)
        item.add(self.lib)

        log = Mock()
        try:
            MPDStats(self.lib, log).run()
        except KeyboardInterrupt:
            pass

        log.debug.assert_has_calls([call('unhandled status "{}"', ANY)])
        log.info.assert_has_calls(
            [call("pause"), call("playing {}", ANY), call("stop")]
        )

    @patch("beetsplug.mpdstats.MPDStats.run")
    def test_cli_options_override_config(self, run_mock):
        self.run_command(
            "mpdstats",
            "--host",
            "somehost",
            "--port",
            "5000",
            "--password",
            "secret",
        )

        assert mpd_config["host"].as_str() == "somehost"
        assert mpd_config["port"].get(int) == 5000
        assert mpd_config["password"].as_str() == "secret"
        run_mock.assert_called_once_with()
