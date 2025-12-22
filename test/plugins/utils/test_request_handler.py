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
        monkeypatch.setattr(
            "urllib3.connectionpool.HTTPConnectionPool._make_request",
            Mock(
                side_effect=[
                    NewConnectionError(None, "Connection failed"),
                    URLError("bad"),
                    last_response,
                ]
            ),
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
        "last_response", [ConnectionResetError], ids=["conn_error"]
    )
    def test_retry_exhaustion(self, request_handler):
        """Verify that the handler raises an error after exhausting retries."""
        with pytest.raises(
            requests.exceptions.ConnectionError, match="Max retries exceeded"
        ):
            request_handler.get("http://example.com/api")
