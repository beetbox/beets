"""Test module for file ui/__init__.py"""

import os
import shutil
import sqlite3
import unittest
from copy import deepcopy
from random import random
from unittest import mock

import pytest

from beets import config, library, ui
from beets.exceptions import UserError
from beets.test import _common
from beets.test.helper import BeetsTestCase, IOMixin


class InputMethodsTest(IOMixin, unittest.TestCase):
    def _print_helper(self, s):
        print(s)

    def _print_helper2(self, s, prefix):
        print(prefix, s)

    def test_input_select_objects(self):
        full_items = ["1", "2", "3", "4", "5"]

        # Test no
        self.io.addinput("n")
        items = ui.input_select_objects(
            "Prompt", full_items, self._print_helper
        )
        assert items == []

        # Test yes
        self.io.addinput("y")
        items = ui.input_select_objects(
            "Prompt", full_items, self._print_helper
        )
        assert items == full_items

        # Test selective 1
        self.io.addinput("s")
        self.io.addinput("n")
        self.io.addinput("y")
        self.io.addinput("n")
        self.io.addinput("y")
        self.io.addinput("n")
        items = ui.input_select_objects(
            "Prompt", full_items, self._print_helper
        )
        assert items == ["2", "4"]

        # Test selective 2
        self.io.addinput("s")
        self.io.addinput("y")
        self.io.addinput("y")
        self.io.addinput("n")
        self.io.addinput("y")
        self.io.addinput("n")
        items = ui.input_select_objects(
            "Prompt", full_items, lambda s: self._print_helper2(s, "Prefix")
        )
        assert items == ["1", "2", "4"]

        # Test selective 3
        self.io.addinput("s")
        self.io.addinput("y")
        self.io.addinput("n")
        self.io.addinput("y")
        self.io.addinput("q")
        items = ui.input_select_objects(
            "Prompt", full_items, self._print_helper
        )
        assert items == ["1", "3"]


class ParentalDirCreation(IOMixin, BeetsTestCase):
    def test_create_yes(self):
        non_exist_path = _common.os.fsdecode(
            os.path.join(self.temp_dir, b"nonexist", str(random()).encode())
        )
        # Deepcopy instead of recovering because exceptions might
        # occur; wish I can use a golang defer here.
        test_config = deepcopy(config)
        test_config["library"] = non_exist_path
        self.io.addinput("y")
        lib = ui._open_library(test_config)
        lib._close()

    def test_create_no(self):
        non_exist_path_parent = _common.os.fsdecode(
            os.path.join(self.temp_dir, b"nonexist")
        )
        non_exist_path = _common.os.fsdecode(
            os.path.join(non_exist_path_parent.encode(), str(random()).encode())
        )
        test_config = deepcopy(config)
        test_config["library"] = non_exist_path

        self.io.addinput("n")
        try:
            lib = ui._open_library(test_config)
        except UserError:
            if os.path.exists(non_exist_path_parent):
                shutil.rmtree(non_exist_path_parent)
                raise OSError("Parent directories should not be created.")
        else:
            if lib:
                lib._close()
            raise OSError("Parent directories should not be created.")


class DatabaseErrorTest(BeetsTestCase):
    """Test database error handling with improved error messages."""

    def test_database_error_with_unable_to_open(self):
        """Test error message when database fails with 'unable to open' error."""
        test_config = deepcopy(config)
        test_config["library"] = _common.os.fsdecode(
            os.path.join(self.temp_dir, b"test.db")
        )

        # Mock Library to raise OperationalError with "unable to open"
        with mock.patch.object(
            library,
            "Library",
            side_effect=sqlite3.OperationalError(
                "unable to open database file"
            ),
        ):
            with pytest.raises(UserError) as cm:
                ui._open_library(test_config)

            error_message = str(cm.value)
            # Should mention permissions and directory
            assert "directory" in error_message.lower()
            assert "writable" in error_message.lower()
            assert "permissions" in error_message.lower()

    def test_database_error_fallback(self):
        """Test fallback error message for other database errors."""
        test_config = deepcopy(config)
        test_config["library"] = _common.os.fsdecode(
            os.path.join(self.temp_dir, b"test.db")
        )

        # Mock Library to raise a different OperationalError
        with mock.patch.object(
            library,
            "Library",
            side_effect=sqlite3.OperationalError("disk I/O error"),
        ):
            with pytest.raises(UserError) as cm:
                ui._open_library(test_config)

            error_message = str(cm.value)
            # Should contain the error but not the permissions message
            assert "could not be opened" in error_message
            assert "disk I/O error" in error_message
            # Should NOT have the permissions-related message
            assert "permissions" not in error_message.lower()
