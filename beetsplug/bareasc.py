#
# This module is adapted from Fuzzy in accordance to the licence of
# that module

"""Provides a bare-ASCII matching query."""

from unidecode import unidecode

from beets import ui
from beets.dbcore.query import StringFieldQuery
from beets.plugins import BeetsPlugin
from beets.ui import print_


class BareascQuery(StringFieldQuery[str]):
    """Compare items using bare ASCII, without accents etc."""

    @classmethod
    def string_match(cls, pattern, val):
        """Convert both pattern and string to plain ASCII before matching.

        If pattern is all lower case, also convert string to lower case so
        match is also case insensitive
        """
        # smartcase
        if pattern.islower():
            val = val.lower()
        pattern = unidecode(pattern)
        val = unidecode(val)
        return pattern in val

    def col_clause(self):
        """Compare ascii version of the pattern."""
        clause = f"unidecode({self.field})"
        if self.pattern.islower():
            clause = f"lower({clause})"

        return rf"{clause} LIKE ? ESCAPE '\'", [f"%{unidecode(self.pattern)}%"]


class BareascPlugin(BeetsPlugin):
    """Plugin to provide bare-ASCII option for beets matching."""

    def __init__(self):
        """Default prefix for selecting bare-ASCII matching is #."""
        super().__init__()
        self.config.add({"prefix": "#"})

    def queries(self):
        """Register bare-ASCII matching."""
        prefix = self.config["prefix"].as_str()
        return {prefix: BareascQuery}

    def commands(self):
        """Add bareasc command as unidecode version of 'list'."""
        cmd = ui.Subcommand(
            "bareasc", help="unidecode version of beet list command"
        )
        cmd.parser.usage += (
            "\nExample: %prog -f '$album: $title' artist:beatles"
        )
        cmd.parser.add_all_common_options()
        cmd.func = self.unidecode_list
        return [cmd]

    def unidecode_list(self, lib, opts, args):
        """Emulate normal 'list' command but with unidecode output."""
        album = opts.album
        # Copied from commands.py - list_items
        if album:
            for album in lib.albums(args):
                bare = unidecode(str(album))
                print_(bare)
        else:
            for item in lib.items(args):
                bare = unidecode(str(item))
                print_(bare)
