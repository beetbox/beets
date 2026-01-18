import os
import subprocess
import sys

import pytest

from beets.test import _common
from beets.test.helper import IOMixin, has_program
from beets.ui.commands.completion import BASH_COMPLETION_PATHS
from beets.util import syspath

from ..test_ui import TestPluginTestCase


@_common.slow_test()
@pytest.mark.xfail(
    os.environ.get("GITHUB_ACTIONS") == "true" and sys.platform == "linux",
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
        if not has_program(cmd[0]):
            self.skipTest("bash not available")
        tester = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env
        )

        # Load bash_completion library.
        for path in BASH_COMPLETION_PATHS:
            if os.path.exists(syspath(path)):
                bash_completion = path
                break
        else:
            self.skipTest("bash-completion script not found")
        try:
            with open(syspath(bash_completion), "rb") as f:
                tester.stdin.writelines(f)
        except OSError:
            self.skipTest("could not read bash-completion script")

        # Load completion script.
        self.run_command("completion", lib=None)
        completion_script = self.io.getoutput().encode("utf-8")
        self.io.restore()
        tester.stdin.writelines(completion_script.splitlines(True))

        # Load test suite.
        test_script_name = os.path.join(_common.RSRC, b"test_completion.sh")
        with open(test_script_name, "rb") as test_script_file:
            tester.stdin.writelines(test_script_file)
        out, _ = tester.communicate()
        assert tester.returncode == 0
        assert out == b"completion tests passed\n", (
            "test/test_completion.sh did not execute properly. "
            f"Output:{out.decode('utf-8')}"
        )
