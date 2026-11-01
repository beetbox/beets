"""Tests for the 'badfiles' plugin."""

from subprocess import DEVNULL
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

    def test_run_command_detaches_stdin(self):
        # The checker commands are non-interactive; run_command must detach
        # stdin from the terminal so a checker cannot leave the TTY in a
        # modified state (e.g. with echo disabled). See #6750.
        plugin = BadFiles()

        with patch(
            "beetsplug.badfiles.check_output", return_value=b""
        ) as mock_check_output:
            plugin.run_command(["mp3val", "foo.mp3"])

        assert mock_check_output.call_args.kwargs["stdin"] is DEVNULL


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
