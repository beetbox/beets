"""This module provides the default commands for beets' command-line
interface.
"""

from beets.util.deprecation import deprecate_imports

from .completion import completion_cmd
from .config import config_cmd
from .fields import fields_cmd
from .help import HelpCommand
from .import_ import import_cmd
from .list import list_cmd
from .modify import modify_cmd
from .move import move_cmd
from .remove import remove_cmd
from .stats import stats_cmd
from .update import update_cmd
from .version import version_cmd
from .write import write_cmd


def __getattr__(name: str):
    """Handle deprecated imports."""
    return deprecate_imports(
        __name__,
        {
            "TerminalImportSession": "beets.ui.commands.import_.session",
            "PromptChoice": "beets.util",
        },
        name,
    )


# The list of default subcommands. This is populated with Subcommand
# objects that can be fed to a SubcommandsOptionParser.
default_commands = [
    fields_cmd,
    HelpCommand(),
    import_cmd,
    list_cmd,
    update_cmd,
    remove_cmd,
    stats_cmd,
    version_cmd,
    modify_cmd,
    move_cmd,
    write_cmd,
    config_cmd,
    completion_cmd,
]


__all__ = ["default_commands"]
