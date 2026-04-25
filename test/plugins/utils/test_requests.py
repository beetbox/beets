from unittest.mock import MagicMock

import pytest
import requests

from beetsplug._utils.requests import RateLimitAdapter


def _prepared_request(
    url: str = "https://example.com",
) -> requests.PreparedRequest:
    req = requests.Request("GET", url)
    return req.prepare()


class TestRateLimitAdapter:
    @pytest.mark.parametrize(
        "last_request_time, now, expected_sleep",
        [
            (100.0, 100.0, 0.25),
            (100.0, 100.1, 0.15),
        ],
    )
    def test_send_sleeps_for_remaining_time(
        self, monkeypatch, last_request_time, now, expected_sleep
    ):
        adapter = RateLimitAdapter(rate_limit=0.25)
        request = _prepared_request()

        send_mock = MagicMock(return_value="ok")
        monkeypatch.setattr(
            "beetsplug._utils.requests.HTTPAdapter.send", send_mock
        )

        monkeypatch.setattr(
            "beetsplug._utils.requests.time.monotonic",
            lambda: now,
        )

        sleep_mock = MagicMock()
        monkeypatch.setattr("beetsplug._utils.requests.time.sleep", sleep_mock)

        adapter._last_request_time = last_request_time
        adapter.send(request)

        assert sleep_mock.call_count == 1
        assert sleep_mock.call_args.args[0] == pytest.approx(expected_sleep)
