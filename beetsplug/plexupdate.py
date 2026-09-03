"""Updates a Plex library whenever the beets library is changed.

Plex Home users enter the Plex Token to enable updating, or run
``beet plexupdate --auth`` once to log in via plex.tv: the obtained
device token is stored in a token file next to the beets configuration.
Put something like the following in your config.yaml to configure:
    plex:
        host: localhost
        port: 32400
        token: token
"""

from __future__ import annotations

import json
import time
import uuid
import webbrowser
from contextlib import suppress
from functools import cached_property
from http import HTTPStatus
from json import JSONDecodeError
from typing import TYPE_CHECKING, ClassVar, Protocol
from urllib.parse import urlencode, urljoin

import confuse
import requests

from beets import __version__, ui
from beets.exceptions import UserError
from beets.logging import getLogger
from beets.plugins import BeetsPlugin
from beetsplug._utils.requests import (
    BeetsHTTPError,
    RequestHandler,
    TimeoutAndRetrySession,
)

if TYPE_CHECKING:
    from pathlib import Path

    from beets.library import LibModel, Library
    from beetsplug._typing import JSONDict

log = getLogger("beets.plexupdate")

# plex.tv endpoints used by the interactive PIN based authentication.
PLEX_API = "https://plex.tv/api/v2"
PLEX_AUTH_URL = "https://app.plex.tv/auth#?"


class PlexUpdateCLIOpts(Protocol):
    auth: bool


class PlexSession(TimeoutAndRetrySession):
    """HTTP session for the Plex server and plex.tv with PIN auth.

    Plex does not offer a public OAuth2 flow (bummer). Instead, third-party
    applications authenticate through Plex' PIN flow: the obtained access
    token is exchanged for the token of the local server, which is stored
    and used for updates.

    see https://developer.plex.tv/pms/#section/API-Info/Authenticating-with-Plex
    """

    def __init__(
        self,
        token_path: Path,
        verify: bool = True,
        token_override: str | None = None,
    ) -> None:
        super().__init__()
        self.token_path = token_path
        self.token_override = token_override
        # The token file is read at most once per run; `save_token` is the
        # only writer and keeps the cache in sync.
        self._token_cache: JSONDict | None = None

        # Allow ignoring certificate errors for self-signed certs.
        self.verify = verify

        self.headers.update(
            {
                "accept": "application/json",
                "X-Plex-Product": "beets",
                "X-Plex-Product-Version": __version__,
                "X-Plex-Client-Identifier": self.client_id,
            }
        )

    @property
    def token(self) -> str | None:
        """The auth token: the configured override or the stored token."""
        return self.token_override or self.load_token().get("X-Plex-Token")

    @property
    def client_id(self) -> str:
        """The client identifier used for plex.tv authentication.

        Either load from the token file or generate a new one and persist it
        on first use.
        """
        data = self.load_token()
        if client_id := data.get("client_identifier"):
            return client_id

        client_id = uuid.uuid4().hex
        data["client_identifier"] = client_id
        self.save_token(data)
        log.debug("Generated and saved new client identifier")
        return client_id

    def load_token(self) -> JSONDict:
        """Load the token data from the token file.

        The contents are cached after the first successful read; a
        not-yet-existing file is re-checked until it appears.
        """
        if self._token_cache is None:
            with suppress(FileNotFoundError, JSONDecodeError, OSError):
                self._token_cache = json.loads(self.token_path.read_text())

        return self._token_cache or {}

    def save_token(self, data: JSONDict) -> None:
        """Merge data into the token file and persist it."""
        token = self.load_token()
        token.update(data)
        self.token_path.write_text(json.dumps(token, indent=2))

    def request(self, *args, **kwargs) -> requests.Response:
        """Send a request, attaching the auth token."""
        headers = kwargs.setdefault("headers", {})
        if token := self.token:
            headers["X-Plex-Token"] = token
        return super().request(*args, **kwargs)

    def create_pin(self) -> JSONDict:
        """Create a pin that yields the user's access token after
        authorization."""
        return (
            super()
            .request("post", f"{PLEX_API}/pins", params={"strong": True})
            .json()
        )

    def wait_for_login(
        self,
        pin_id: int,
        timeout: int = 300,  # 5min
    ) -> str | None:
        """Poll the pin endpoint until the user authorized the login.

        Returns the plex.tv account token, or ``None`` on timeout.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data: JSONDict = {}
            with suppress(requests.exceptions.RequestException):
                data = (
                    super().request("get", f"{PLEX_API}/pins/{pin_id}").json()
                )

            if token := data.get("authToken"):
                return token

            log.debug("Plex pin polling failed. Retrying in 5s...")
            time.sleep(5)  # 5s polling
        return None


class UnauthorizedPlexError(BeetsHTTPError):
    """The Plex server rejected the request (401)."""

    STATUS = HTTPStatus.UNAUTHORIZED

    def __init__(self, *args, message: str | None = None, **kwargs) -> None:
        message = (
            f"HTTP Error: {self.STATUS.value} {self.STATUS.phrase}. "
            "You may need to reauthenticate using `beet plexupdate --auth`."
        )
        super().__init__(*args, message=message, **kwargs)


class PlexAPI(RequestHandler):
    """API client for Plex.

    Wraps the interactive plex.tv PIN authentication flow and the local
    server API used to refresh the music library; the session deals with
    the HTTP requests to plex.tv, token persistence and the PIN flow.
    """

    explicit_http_errors: ClassVar[list[type[BeetsHTTPError]]] = [
        UnauthorizedPlexError
    ]

    def __init__(
        self,
        token_path: Path,
        host: str,
        port: int,
        library_name: str,
        secure: bool,
        verify: bool,
        token_override: str | None = None,
    ) -> None:
        self.token_path = token_path
        self.token_override = token_override
        self.library_name = library_name

        self.base_url = f"{'https' if secure else 'http'}://{host}:{port}/"
        self._verify = verify

    @cached_property
    def session(self) -> PlexSession:
        """Session with token persistence and plex.tv identifying headers."""
        return PlexSession(
            token_path=self.token_path,
            verify=self._verify,
            token_override=self.token_override,
        )

    def ui_authenticate_flow(self) -> None:
        """Interactive authentication with plex.tv (PIN flow).

        1. Open the authentication URL in the browser
        2. Wait for the user to authorize (~5 minutes)
        3. Token is auto-saved for future use
        """
        try:
            pin = self.session.create_pin()
        except requests.exceptions.RequestException as e:
            raise UserError(f"Plex login flow failed: {e}") from e

        auth_url = PLEX_AUTH_URL + urlencode(
            {
                "clientID": self.session.client_id,
                "code": pin["code"],
                "context[device][product]": "beets",
            }
        )
        ui.print_(f"Please visit: {auth_url}")
        ui.print_("Waiting for authorization in your browser...")
        with suppress(webbrowser.Error):
            webbrowser.open(auth_url)

        if not (account_token := self.session.wait_for_login(pin["id"])):
            raise UserError(
                "Plex authentication timed out. Please run "
                "`beet plexupdate --auth` again."
            )

        # The pin flow token works for plex.tv and the local server
        # alike, so it is stored directly.
        self.session.save_token({"X-Plex-Token": account_token})
        ui.print_(
            f"Authentication successful! Token saved to {self.token_path}."
        )

    def get_music_section(self) -> str | None:
        """The section key for the music library in Plex."""
        data = self.get_json(urljoin(self.base_url, "library/sections"))

        # Find the section with the configured name and return its key.
        for directory in data.get("MediaContainer", {}).get("Directory", []):
            if directory.get("title") == self.library_name:
                return str(directory["key"])
        return None

    def update_library(self) -> requests.Response:
        """Start a refresh of the music library."""
        section_key = self.get_music_section()
        if section_key is None:
            raise UserError(
                f"No music library named {self.library_name!r} found on "
                "the Plex server. Check the `plex.library_name` setting."
            )

        return self.get(
            urljoin(self.base_url, f"library/sections/{section_key}/refresh")
        )


class PlexUpdate(BeetsPlugin):
    def __init__(self) -> None:
        # Set name so the config is available under `plex:` in config.yaml
        super().__init__("plex")
        self.config.add(
            {
                "host": "localhost",
                "port": 32400,
                "library_name": "Music",
                "secure": False,
                "ignore_cert_errors": False,
                "tokenfile": "plex_token.json",
                # Deprecated: use `beet plexupdate --auth` instead.
                "token": "",
            }
        )
        self.config["token"].redact = True

        # `cli_exit` is registered lazily on the first library change so
        # read-only operations skip the refresh.
        self._registered = False
        self.register_listener("database_change", self.listen_for_db_change)

    @cached_property
    def api(self) -> PlexAPI:
        """API client for plex.tv authentication and the local server."""
        return PlexAPI(
            token_path=self._tokenfile(),
            host=self.config["host"].get(str),
            port=self.config["port"].get(),
            library_name=self.config["library_name"].get(),
            secure=self.config["secure"].get(bool),
            verify=not self.config["ignore_cert_errors"].get(bool),
            token_override=self.config["token"].get(str) or None,
        )

    def _tokenfile(self) -> Path:
        """Path to the JSON file holding the plex.tv auth token."""
        return self.config["tokenfile"].get(confuse.Path(in_app_dir=True))

    def listen_for_db_change(self, lib: Library, model: LibModel) -> None:
        """Register the exit-time Plex refresh on the first library change."""
        if not self._registered:
            self.register_listener("cli_exit", self.update)
            self._registered = True

    def update(self, lib: Library) -> None:
        """Send a refresh request to the Plex server when the client exits."""
        log.info("Updating Plex library...")

        try:
            self.api.update_library()
            log.info("Started library update successfully.")
        except UserError as e:
            log.exception("Plex library update failed: %s", e)
        except UnauthorizedPlexError:
            log.error(
                "Plex library update failed: the server rejected the "
                "request (401). If it requires authentication, run "
                "`beet plexupdate --auth`."
            )
        except requests.exceptions.RequestException:
            log.exception("Library update failed!")

    def commands(self) -> list[ui.Subcommand]:
        plexupdate_cmd = ui.Subcommand(
            "plexupdate", help="Update Plex library when beets library changes"
        )
        plexupdate_cmd.parser.add_option(
            "-a",
            "--auth",
            action="store_true",
            help="Authenticate and login to Plex",
            default=False,
        )

        def auth_func(
            lib: Library, opts: PlexUpdateCLIOpts, args: list[str]
        ) -> None:
            if opts.auth:
                self.api.ui_authenticate_flow()
            else:
                plexupdate_cmd.print_help()

        plexupdate_cmd.func = auth_func

        return [plexupdate_cmd]
