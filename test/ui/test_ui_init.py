"""Test module for file ui/__init__.py"""

import unittest
from copy import deepcopy
from pathlib import Path
from random import random
from unittest import mock

import pytest

from beets import config, ui
from beets.exceptions import UserError
from beets.test.helper import BeetsTestCase, IOMixin


class InputMethodsTest(IOMixin, unittest.TestCase):
    def _print_helper(self, s):
        print(s)

    def _print_helper2(self, s, prefix):
        print(prefix, s)

    def test_input_unicode_decode_error_raises_user_error(self):
        """
        Regression test for
        https://github.com/beetbox/beets/issues/3651

        Malformed terminal input bytes (e.g. from a terminal/paste
        glitch) can make the builtin input() raise UnicodeDecodeError.
        This must be converted to a clean UserError -- matching the
        existing handling for EOFError just above it -- rather than
        propagating an unhandled UnicodeDecodeError and crashing the
        whole import session.
        """

        def raise_unicode_decode_error(*args, **kwargs):
            raise UnicodeDecodeError(
                "utf-8", b"\xe3\x81\x82\x82", 3, 4, "invalid continuation byte"
            )

        with mock.patch("builtins.input", side_effect=raise_unicode_decode_error):
            with pytest.raises(UserError):
                ui.input_("Artist:")

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
    def test_memory_path_skips_creation_prompt(self):
        ui._ensure_db_directory_exists(Path(":memory:"))
        assert not self.io.getoutput()

    def test_create_yes(self):
        non_exist_path = self.temp_path / "nonexist" / str(random())
        # Deepcopy instead of recovering because exceptions might
        # occur; wish I can use a golang defer here.
        test_config = deepcopy(config)
        test_config["library"] = str(non_exist_path)
        self.io.addinput("y")
        lib = ui._open_library(test_config)
        lib._close()

    def test_create_no(self):
        non_exist_path_parent = self.temp_path / "nonexist"
        non_exist_path = non_exist_path_parent / str(random())
        test_config = deepcopy(config)
        test_config["library"] = str(non_exist_path)

        self.io.addinput("n")
        with pytest.raises(UserError):
            ui._open_library(test_config)
        assert not non_exist_path_parent.exists()
