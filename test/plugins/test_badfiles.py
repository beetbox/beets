# This file is part of beets.
# Copyright 2026, Eyup Akman.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Tests for the 'badfiles' plugin."""

from types import SimpleNamespace
from unittest.mock import patch

from beets import importer
from beets.test.helper import PluginTestCase
from beetsplug.badfiles import BadFiles


class BadFilesPluginTest(PluginTestCase):
    plugin = "badfiles"

    def test_quiet_import_skips_prompt(self):
        plugin = BadFiles()
        task = SimpleNamespace(_badfiles_checks_failed=[["bad: error"]])

        self.config["import"]["quiet"] = True

        with patch("beetsplug.badfiles.ui.input_options", return_value="s"):
            result = plugin.on_import_task_before_choice(task, session=None)

        assert result is None

    def test_non_quiet_import_calls_prompt(self):
        plugin = BadFiles()
        task = SimpleNamespace(_badfiles_checks_failed=[["bad: error"]])

        self.config["import"]["quiet"] = False

        with patch("beetsplug.badfiles.ui.input_options", return_value="s"):
            result = plugin.on_import_task_before_choice(task, session=None)

        assert result == importer.Action.SKIP
