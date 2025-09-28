import atexit
from http import HTTPStatus

import requests

from beets import __version__


class NotFoundError(requests.exceptions.HTTPError):
    pass


class CaptchaError(requests.exceptions.HTTPError):
    pass


class TimeoutSession(requests.Session):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers["User-Agent"] = f"beets/{__version__} https://beets.io/"

        @atexit.register
        def close_session():
            """Close the requests session on shut down."""
            self.close()

    def request(self, *args, **kwargs):
        """Wrap the request method to raise an exception on HTTP errors."""
        kwargs.setdefault("timeout", 10)
        r = super().request(*args, **kwargs)
        if r.status_code == HTTPStatus.NOT_FOUND:
            raise NotFoundError("HTTP Error: Not Found", response=r)
        if 300 <= r.status_code < 400:
            raise CaptchaError("Captcha is required", response=r)

        r.raise_for_status()

        return r
