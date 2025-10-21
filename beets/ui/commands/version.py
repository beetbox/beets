"""The 'version' command: show version information."""

from platform import python_version

import beets
from beets import plugins, ui


def show_version(*args):
    ui.print_(f"beets version {beets.__version__}")
    ui.print_(f"Python version {python_version()}")
    # Show plugins.
    names = sorted(p.name for p in plugins.find_plugins())
    if names:
        ui.print_("plugins:", ", ".join(names))
    else:
        ui.print_("no plugins loaded")


version_cmd = ui.Subcommand("version", help="output version information")
version_cmd.func = show_version

__all__ = ["version_cmd"]
