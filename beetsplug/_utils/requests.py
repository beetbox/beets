from __future__ import annotations

import atexit
import threading
from contextlib import contextmanager
from functools import cached_property
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Protocol, TypeVar

import requests

from beets import __version__

if TYPE_CHECKING:
    from collections.abc import Iterator


class BeetsHTTPError(requests.exceptions.HTTPError):
    STATUS: ClassVar[HTTPStatus]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            f"HTTP Error: {self.STATUS.value} {self.STATUS.phrase}",
            *args,
            **kwargs,
        )


class HTTPNotFoundError(BeetsHTTPError):
    STATUS = HTTPStatus.NOT_FOUND


class Closeable(Protocol):
    """Protocol for objects that have a close method."""

    def close(self) -> None: ...


C = TypeVar("C", bound=Closeable)


class SingletonMeta(type, Generic[C]):
    """Metaclass ensuring a single shared instance per class.

    Creates one instance per class type on first instantiation, reusing it
    for all subsequent calls. Automatically registers cleanup on program exit
    for proper resource management.
    """

    _instances: ClassVar[dict[type[Any], Any]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> C:
        if cls not in cls._instances:
            with cls._lock:
                if cls not in SingletonMeta._instances:
                    instance = super().__call__(*args, **kwargs)
                    SingletonMeta._instances[cls] = instance
                    atexit.register(instance.close)
        return SingletonMeta._instances[cls]


class TimeoutSession(requests.Session, metaclass=SingletonMeta):
    """HTTP session with automatic timeout and status checking.

    Extends requests.Session to provide sensible defaults for beets HTTP
    requests: automatic timeout enforcement, status code validation, and
    proper user agent identification.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers["User-Agent"] = f"beets/{__version__} https://beets.io/"

    def request(self, *args, **kwargs):
        """Execute HTTP request with automatic timeout and status validation.

        Ensures all requests have a timeout (defaults to 10 seconds) and raises
        an exception for HTTP error status codes.
        """
        kwargs.setdefault("timeout", 10)
        r = super().request(*args, **kwargs)
        r.raise_for_status()

        return r


class RequestHandler:
    """Manages HTTP requests with custom error handling and session management.

    Provides a reusable interface for making HTTP requests with automatic
    conversion of standard HTTP errors to beets-specific exceptions. Supports
    custom session types and error mappings that can be overridden by
    subclasses.

    Usage:
        Subclass and override :class:`RequestHandler.session_type`,
        :class:`RequestHandler.explicit_http_errors` or
        :class:`RequestHandler.status_to_error()` to customize behavior.

        Use
        * :class:`RequestHandler.get_json()` to get JSON response data
        * :class:`RequestHandler.get()` to get HTTP response object
        * :class:`RequestHandler.request()` to invoke arbitrary HTTP methods

        Feel free to define common methods that are used in multiple plugins.
    """

    session_type: ClassVar[type[TimeoutSession]] = TimeoutSession
    explicit_http_errors: ClassVar[list[type[BeetsHTTPError]]] = [
        HTTPNotFoundError
    ]

    @cached_property
    def session(self) -> Any:
        """Lazily initialize and cache the HTTP session."""
        return self.session_type()

    def status_to_error(
        self, code: int
    ) -> type[requests.exceptions.HTTPError] | None:
        """Map HTTP status codes to beets-specific exception types.

        Searches the configured explicit HTTP errors for a matching status code.
        Returns None if no specific error type is registered for the given code.
        """
        return next(
            (e for e in self.explicit_http_errors if e.STATUS == code), None
        )

    @contextmanager
    def handle_http_error(self) -> Iterator[None]:
        """Convert standard HTTP errors to beets-specific exceptions.

        Wraps operations that may raise HTTPError, automatically translating
        recognized status codes into their corresponding beets exception types.
        Unrecognized errors are re-raised unchanged.
        """
        try:
            yield
        except requests.exceptions.HTTPError as e:
            if beets_error := self.status_to_error(e.response.status_code):
                raise beets_error(response=e.response) from e
            raise

    def request(self, *args, **kwargs) -> requests.Response:
        """Perform HTTP request using the session with automatic error handling.

        Delegates to the underlying session method while converting recognized
        HTTP errors to beets-specific exceptions through the error handler.
        """
        with self.handle_http_error():
            return self.session.request(*args, **kwargs)

    def get(self, *args, **kwargs) -> requests.Response:
        """Perform HTTP GET request with automatic error handling."""
        return self.request("get", *args, **kwargs)

    def get_json(self, *args, **kwargs):
        """Fetch and parse JSON data from an HTTP endpoint."""
        return self.get(*args, **kwargs).json()
