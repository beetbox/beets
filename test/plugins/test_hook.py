from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import pytest

from beets import plugins
from beets.test.helper import PluginTestHelper

if TYPE_CHECKING:
    from collections.abc import Callable


class HookTestCase(PluginTestHelper):
    plugin = "hook"
    preload_plugin = False

    def _get_hook(self, event: str, command: str) -> dict[str, str]:
        return {"event": event, "command": command}


class TestHookLogs(HookTestCase):
    HOOK: plugins.EventType = "write"

    def _configure_hook(self, command: str) -> None:
        config = {"hooks": [self._get_hook(self.HOOK, command)]}

        with self.configure_plugin(config):
            plugins.send(self.HOOK)

    def test_hook_empty_command(self, caplog: pytest.LogCaptureFixture):
        with caplog.at_level("DEBUG"):
            self._configure_hook("")

        assert 'invalid command ""' in caplog.messages

    # FIXME: fails on windows
    @pytest.mark.skipif(sys.platform == "win32", reason="win32")
    def test_hook_non_zero_exit(self, caplog: pytest.LogCaptureFixture):
        with caplog.at_level("DEBUG"):
            self._configure_hook('sh -c "exit 1"')

        assert f"hook for {self.HOOK} exited with status 1" in caplog.messages

    def test_hook_non_existent_command(self, caplog: pytest.LogCaptureFixture):
        with caplog.at_level("DEBUG"):
            self._configure_hook("non-existent-command")
        assert f"hook for {self.HOOK} failed: " in caplog.text
        # The error message is different for each OS. Unfortunately the text is
        # different in each case, where the only shared text is the string
        # 'file' and substring 'Err'
        assert "Err" in caplog.text
        assert "file" in caplog.text


class TestHookCommand(HookTestCase):
    EVENTS: ClassVar[list[plugins.EventType]] = ["write", "after_write"]

    @pytest.fixture(autouse=True)
    def setUp(self):
        self.paths = [str(self.temp_path / e) for e in self.EVENTS]

    def _test_command(
        self,
        make_test_path: Callable[[str, str], str],
        send_path_kwarg: bool = False,
    ) -> None:
        """Check that each of the configured hooks is executed.

        Configure hooks for each event:
        1. Use the given 'make_test_path' callable to create a test path from the event
           and the original path.
        2. Configure a hook with a command to touch this path.

        For each of the original paths:
        1. Send a test event
        2. Assert that a file has been created under the original path, which proves
           that the configured hook command has been executed.
        """
        events_with_paths = list(zip(self.EVENTS, self.paths))
        hooks = [
            self._get_hook(e, f"touch {make_test_path(e, p)}")
            for e, p in events_with_paths
        ]

        with self.configure_plugin({"hooks": hooks}):
            for event, path in events_with_paths:
                if send_path_kwarg:
                    plugins.send(event, path=path)
                else:
                    plugins.send(event)
                assert Path(os.fsdecode(path)).is_file()

    @pytest.mark.skipif(sys.platform == "win32", reason="win32")
    def test_hook_no_arguments(self):
        self._test_command(lambda _, p: p)

    @pytest.mark.skipif(sys.platform == "win32", reason="win32")
    def test_hook_event_substitution(self):
        self._test_command(lambda e, p: p.replace(e, "{event}"))

    @pytest.mark.skipif(sys.platform == "win32", reason="win32")
    def test_hook_argument_substitution(self):
        self._test_command(lambda *_: "{path}", send_path_kwarg=True)

    @pytest.mark.skipif(sys.platform == "win32", reason="win32")
    def test_hook_bytes_interpolation(self):
        self.paths = [p.encode() for p in self.paths]
        self._test_command(lambda *_: "{path}", send_path_kwarg=True)
