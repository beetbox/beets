"""The 'help' command: show help information for commands."""

from beets.ui._common import UserError
from beets.ui.core import Subcommand


class HelpCommand(Subcommand):
    def __init__(self):
        super().__init__(
            "help",
            aliases=("?",),
            help="give detailed help on a specific sub-command",
        )

    def func(self, lib, opts, args):
        if args:
            cmdname = args[0]
            helpcommand = self.root_parser._subcommand_for_name(cmdname)
            if not helpcommand:
                raise UserError(f"unknown command '{cmdname}'")
            helpcommand.print_help()
        else:
            self.root_parser.print_help()
