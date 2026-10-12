import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from beets.test import _common
from beets.test.helper import RUNNING_IN_CI, IOMixin
from beets.ui import Subcommand
from beets.ui.commands.completion import BASH_COMPLETION_PATHS, completion_script

from ..test_ui import TestPluginTestCase


@pytest.mark.xfail(
    RUNNING_IN_CI and sys.platform == "linux",
    reason="Completion is for some reason unhappy on Ubuntu 24.04 in CI",
)
class CompletionTest(IOMixin, TestPluginTestCase):
    def test_completion(self):
        # Do not load any other bash completion scripts on the system.
        env = dict(os.environ)
        env["BASH_COMPLETION_DIR"] = os.devnull
        env["BASH_COMPLETION_COMPAT_DIR"] = os.devnull

        # Open a `bash` process to run the tests in. We'll pipe in bash
        # commands via stdin.
        cmd = os.environ.get("BEETS_TEST_SHELL", "/bin/bash --norc").split()
        if not shutil.which(cmd[0]):
            self.skipTest("bash not available")
        tester = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env
        )

        # Load bash_completion library.
        completion_paths = map(Path, map(os.fsdecode, BASH_COMPLETION_PATHS))
        for path in completion_paths:
            if path.exists():
                bash_completion = path
                break
        else:
            self.skipTest("bash-completion script not found")
        try:
            with bash_completion.open("rb") as f:
                tester.stdin.writelines(f)
        except OSError:
            self.skipTest("could not read bash-completion script")

        # Load completion script.
        self.run_command("completion")
        completion_script_out = self.io.getoutput().encode("utf-8")
        tester.stdin.writelines(completion_script_out.splitlines(True))

        # Load test suite.
        test_script_name = _common.RSRC / "test_completion.sh"
        with test_script_name.open("rb") as test_script_file:
            tester.stdin.writelines(test_script_file)
        out, _ = tester.communicate()
        assert tester.returncode == 0
        assert out == b"completion tests passed\n", (
            "test/test_completion.sh did not execute properly. "
            f"Output:{out.decode('utf-8')}"
        )

    def test_hyphenated_command_names_are_sanitized(self):
        """Regression test for #2836: hyphenated command names must not
        produce invalid bash variable names.

        The completion script generator replaces '-' with '_' in variable
        names so that commands like 'foo-bar' become 'foo_bar' in the
        generated shell variables.
        """
        cmd = Subcommand("foo-bar", aliases=["fb"])
        script = "".join(completion_script([cmd]))

        # Variable names must use underscores, not hyphens.
        assert (
            "alias__foo_bar" in script
            or "opts__foo_bar" in script
            or "flags__foo_bar" in script
        )
        assert "alias__foo-bar" not in script
        assert "opts__foo-bar" not in script
        assert "flags__foo-bar" not in script

        # The original command name should still appear in the commands list.
        assert "foo-bar" in script
