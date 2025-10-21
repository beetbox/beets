"""The 'help' command: show help information for commands."""

from beets import ui


class HelpCommand(ui.Subcommand):
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
                raise ui.UserError(f"unknown command '{cmdname}'")
            helpcommand.print_help()
        else:
            self.root_parser.print_help()
