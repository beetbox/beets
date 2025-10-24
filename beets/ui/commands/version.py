"""The 'version' command: show version information."""

from platform import python_version

import beets
from beets import plugins
from beets.ui.core import Subcommand, print_


def show_version(*args):
    print_(f"beets version {beets.__version__}")
    print_(f"Python version {python_version()}")
    # Show plugins.
    names = sorted(p.name for p in plugins.find_plugins())
    if names:
        print_("plugins:", ", ".join(names))
    else:
        print_("no plugins loaded")


version_cmd = Subcommand("version", help="output version information")
version_cmd.func = show_version

__all__ = ["version_cmd"]
