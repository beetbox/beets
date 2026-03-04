from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import requests

if TYPE_CHECKING:
    from requests_mock import Mocker


@pytest.fixture
def requests_mock(requests_mock, monkeypatch) -> Mocker:
    """Use plain session wherever MB requests are mocked.

    This avoids rate limiting requests to speed up tests.
    """
    monkeypatch.setattr(
        "beetsplug._utils.musicbrainz.MusicBrainzAPI.create_session",
        lambda _: requests.Session(),
    )
    return requests_mock
