# This file is part of beets.
# Copyright 2016, Adrian Sampson.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""This module provides the default commands for beets' command-line
interface.
"""

from beets import plugins

from .completion import register_print_completion
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
    *plugins.commands(),
]


# Register the completion command last as it needs all
# other commands to be present.
register_print_completion(default_commands)

__all__ = ["default_commands"]
