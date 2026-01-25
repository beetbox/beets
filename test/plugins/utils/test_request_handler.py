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
    def patch_connection(self, monkeypatch, last_response):
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
    def test_retry_on_connection_error(self, request_handler):
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
    def test_retry_exhaustion(self, request_handler):
        """Verify that the handler raises an error after exhausting retries."""
        with pytest.raises(
            requests.exceptions.RequestException, match="Max retries exceeded"
        ):
            request_handler.get("http://example.com/api")
