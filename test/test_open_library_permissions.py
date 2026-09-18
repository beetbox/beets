# This file is part of beets.
# Copyright 2026.
"""Permission-related database open error messages."""

from __future__ import annotations

import sqlite3
from unittest import mock

import pytest

from beets import config
from beets.test.helper import BeetsTestCase
from beets.ui import UserError, _open_library


class OpenLibraryPermissionsTest(BeetsTestCase):
    def test_unable_to_open_gets_permissions_hint(self):
        with mock.patch(
            "beets.library.Library",
            side_effect=sqlite3.OperationalError("unable to open database file"),
        ):
            with pytest.raises(UserError, match="permissions"):
                _open_library(config)

    def test_readonly_gets_permissions_hint(self):
        with mock.patch(
            "beets.library.Library",
            side_effect=sqlite3.OperationalError(
                "attempt to write a readonly database"
            ),
        ):
            with pytest.raises(UserError, match="permissions"):
                _open_library(config)
