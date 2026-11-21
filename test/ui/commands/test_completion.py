import os
import shutil
import subprocess

import pytest

from beets.test import _common
from beets.test.helper import RUNNING_IN_CI, IOMixin
from beets.ui.commands.completion import BASH_COMPLETION_PATH

from ..test_ui import TestPluginTestCase


@pytest.mark.skipif(
    not BASH_COMPLETION_PATH and not RUNNING_IN_CI,
    reason="bash-completion package not available and not running in CI environment",
)
class CompletionTest(IOMixin, TestPluginTestCase):
    def test_completion(self):
        # Do not load any other bash completion scripts on the system.
        env = dict(os.environ)
        env["BASH_COMPLETION_DIR"] = os.devnull
        env["BASH_COMPLETION_COMPAT_DIR"] = os.devnull

        completion_dir = self.temp_path / "completion"
        completion_dir.mkdir()
        (completion_dir / "completion-file").touch()
        (completion_dir / "completion-directory").mkdir()

        assert BASH_COMPLETION_PATH is not None

        # Build the script before starting Bash so setup errors cannot leave a
        # child process holding the temporary working directory open.
        contents = BASH_COMPLETION_PATH.read_bytes()

        self.run_command("completion")
        contents += self.io.getoutput().encode("utf-8")

        test_script_name = _common.RSRC / "test_completion.sh"
        contents += test_script_name.read_bytes()

        cmd = os.environ.get(
            "BEETS_TEST_SHELL", f"{shutil.which('bash')} --norc"
        ).split()
        tester = subprocess.run(
            cmd,
            input=contents,
            stdout=subprocess.PIPE,
            env=env,
            cwd=completion_dir,
        )
        assert tester.returncode == 0
        assert tester.stdout == b"completion tests passed\n", (
            "test/test_completion.sh did not execute properly. "
            f"Output:{tester.stdout.decode('utf-8')}"
        )
