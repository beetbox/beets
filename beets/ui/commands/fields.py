"""The `fields` command: show available fields for queries and format strings."""

import textwrap

from beets import library
from beets.ui.core import Subcommand, print_


def _print_keys(query):
    """Given a SQLite query result, print the `key` field of each
    returned row, with indentation of 2 spaces.
    """
    for row in query:
        print_(f"  {row['key']}")


def fields_func(lib, opts, args):
    def _print_rows(names):
        names.sort()
        print_(textwrap.indent("\n".join(names), "  "))

    print_("Item fields:")
    _print_rows(library.Item.all_keys())

    print_("Album fields:")
    _print_rows(library.Album.all_keys())

    with lib.transaction() as tx:
        # The SQL uses the DISTINCT to get unique values from the query
        unique_fields = "SELECT DISTINCT key FROM ({})"

        print_("Item flexible attributes:")
        _print_keys(tx.query(unique_fields.format(library.Item._flex_table)))

        print_("Album flexible attributes:")
        _print_keys(tx.query(unique_fields.format(library.Album._flex_table)))


fields_cmd = Subcommand(
    "fields", help="show fields available for queries and format strings"
)
fields_cmd.func = fields_func
