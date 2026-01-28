import io
from http import HTTPStatus
from unittest.mock import Mock
from urllib.error import URLError

import pytest
import requests
from urllib3 import HTTPResponse
from urllib3.exceptions import NewConnectionError

from beetsplug._utils.requests import RequestHandler


class TestRequestHandlerRetry:
    @pytest.fixture(autouse=True)
    def patch_connection(self, monkeypatch, request):
        callspec = getattr(request.node, "callspec", None)
        if callspec is None or "last_response" not in callspec.params:
            return

        last_response = callspec.params["last_response"]

        def make_response():
            if isinstance(last_response, HTTPResponse):
                body = last_response.data
                return HTTPResponse(
                    body=io.BytesIO(body),
                    status=last_response.status,
                    preload_content=False,
                    headers=last_response.headers,
                )
            return last_response

        def responses():
            yield NewConnectionError(None, "Connection failed")
            yield URLError("bad")
            while True:
                yield make_response()

        monkeypatch.setattr(
            "urllib3.connectionpool.HTTPConnectionPool._make_request",
            Mock(side_effect=responses()),
        )

    @pytest.fixture
    def request_handler(self):
        return RequestHandler()

    @pytest.mark.parametrize(
        "last_response",
        [
            HTTPResponse(
                body=io.BytesIO(b"success"),
                status=HTTPStatus.OK,
                preload_content=False,
            ),
        ],
        ids=["success"],
    )
    def test_retry_on_connection_error(self, request_handler, last_response):
        """Verify that the handler retries on connection errors."""
        response = request_handler.get("http://example.com/api")

        assert response.text == "success"
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.parametrize(
        "last_response",
        [
            ConnectionResetError,
            HTTPResponse(
                body=io.BytesIO(b"Server Error"),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                preload_content=False,
            ),
        ],
        ids=["conn_error", "server_error"],
    )
    def test_retry_exhaustion(self, request_handler, last_response):
        """Verify that the handler raises an error after exhausting retries."""
        with pytest.raises(
            requests.exceptions.RequestException, match="Max retries exceeded"
        ):
            request_handler.get("http://example.com/api")

    def test_retry_config(self, request_handler):
        """Verify that the retry adapter is configured with expected settings."""
        adapter = request_handler.session.get_adapter("http://")
        retry = adapter.max_retries

        assert retry.total == 6
        assert retry.backoff_factor == 0.5
        assert set(retry.status_forcelist) == {
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.SERVICE_UNAVAILABLE,
            HTTPStatus.GATEWAY_TIMEOUT,
        }

    def test_backoff_schedule_doubles(self, request_handler):
        """Verify exponential backoff schedule for consecutive errors."""
        retry = request_handler.session.get_adapter("http://").max_retries
        retry = retry.new(total=None)

        backoffs = []
        for _ in range(7):
            retry = retry.increment(
                error=NewConnectionError(None, "Connection failed")
            )
            backoff = retry.get_backoff_time()
            if backoff:
                backoffs.append(backoff)

        assert backoffs == [2**i for i in range(6)]

    @pytest.mark.parametrize(
        "last_response",
        [
            HTTPResponse(
                body=io.BytesIO(b"Server Error"),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                preload_content=False,
            ),
        ],
        ids=["server_error"],
    )
    def test_retry_backoff_sleep_calls(
        self, request_handler, monkeypatch, last_response
    ):
        """Verify backoff sleep calls without real waiting."""
        sleep_calls = []

        def fake_sleep(duration):
            sleep_calls.append(duration)

        monkeypatch.setattr("urllib3.util.retry.time.sleep", fake_sleep)

        with pytest.raises(
            requests.exceptions.RequestException, match="Max retries exceeded"
        ):
            request_handler.get("http://example.com/api")

        assert sleep_calls == [2**i for i in range(5)]
