"""Tests for the 'badfiles' plugin."""

from types import SimpleNamespace
from unittest.mock import patch

from beets import importer
from beets.test.helper import (
    AutotagImportTestCase,
    PluginMixin,
    PluginTestCase,
    TerminalImportMixin,
)
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


class BadfilesOnImportTest(
    TerminalImportMixin, PluginMixin, AutotagImportTestCase
):
    plugin = "badfiles"

    def setUp(self):
        super().setUp()
        self.prepare_album_for_import(1)
        self.importer = self.setup_importer()

    def test_play_on_import(self):
        BadFiles()
        self.importer.add_choice("b")
        checker = self.temp_path / "checker"
        checker.write_text("#!/bin/sh\nexit 1")
        checker.chmod(0o755)
        with self.configure_plugin(
            {"check_on_import": True, "commands": {"mp3": str(checker)}}
        ):
            self.importer.run()

        assert not self.lib.items()
