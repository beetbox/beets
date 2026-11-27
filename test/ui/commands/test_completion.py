import os
import shutil
import subprocess

import pytest

from beets import ui
from beets.test import _common
from beets.test.helper import RUNNING_IN_CI, IOMixin
from beets.ui.commands.completion import BASH_COMPLETION_PATH, completion_script

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


def test_completion_script_hyphenated_command_name():
    """Regression test for #2836.

    Hyphens are not valid in bash variable names, so a command such as
    ``foo-bar`` must produce ``opts__foo_bar`` in the generated script.
    """
    cmd = ui.Subcommand("foo-bar", help="dummy command")
    cmd.parser.add_option("--some-opt", help="an option")

    script = "".join(completion_script([cmd]))

    assert "local opts__foo_bar=" in script
    assert "opts__foo-bar" not in script
