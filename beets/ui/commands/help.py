"""The 'help' command: show help information for commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from beets import ui
from beets.exceptions import UserError

if TYPE_CHECKING:
    import optparse

    from beets.library import Library


class HelpCommand(ui.Subcommand):
    def __init__(self) -> None:
        super().__init__(
            "help",
            aliases=("?",),
            help="give detailed help on a specific sub-command",
        )

    def func(
        self, lib: Library, opts: optparse.Values, args: list[str]
    ) -> None:
        assert isinstance(self.root_parser, ui.SubcommandsOptionParser)
        if args:
            cmdname = args[0]
            helpcommand = self.root_parser._subcommand_for_name(cmdname)
            if not helpcommand:
                raise UserError(f"unknown command '{cmdname}'")
            helpcommand.print_help()
        else:
            self.root_parser.print_help()
