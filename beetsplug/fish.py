# This file is part of beets.
# Copyright 2015, winters jean-marie.
# Copyright 2020, Justin Mayer <https://justinmayer.com>
# Copyright 2024, Arav K. <gq28uu827qlnqpgi@bal-e.org>
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

"""
This plugin provides support for the Fish shell <https://fishshell.com>.

It can be used to generate a completion script, which will then provide the
user with helpful tab completions for the beets CLI, including plugin commands
and options.  While completions for built-in metadata field names are always
generated, completions for known metadata field values (based on the contents
of the database when this plugin is executed) can also be included.  The plugin
automatically writes the script to an appropriate configuration directory for
Fish; no additional user work is needed.

For more information about writing completions for Fish, please see
<https://fishshell.com/docs/current/completions.html>.
"""

import io
import optparse
import os
import textwrap
from pathlib import Path
from typing import Iterable, Optional, cast

import beets.ui.commands
from beets import library, ui
from beets.plugins import BeetsPlugin

# There are many completion scripts provided by Fish itself that dynamically
# load information from the commands they are completing.  For example, the Git
# completion script executes Git on startup to get a list of command aliases.
# While I think such an implementation would be the best-case scenario for us,
# it's not practical due to Beets' high startup overhead (due to Python and due
# to plugins), and because we would have to load information about the commands
# provided by every plugin.  Alternatively, we could have a two-stage process:
# an unchanging completion script that loads a dynamically-updated one, where
# the former provides utility functions and keeps the second one updated, while
# the second one provides the actual completion data.  This is still difficult
# because detecting whether an update is necessary is hard: you'd have to check
# the running Beets version and when the configuration file was last updated.
# The current solution is too simple but anything better would be too complex.
#  -- Arav K., July 2024


# A set of helper items written in Fish itself.
HELPERS = [
    # A description of Beets' global command-line options, allowing us to
    # parse past them and find subcommands in the command-line.
    """
    # An 'argparse' description for global options for 'beet'.
    function __fish_beet_global_optspec
        string join \\n v/verbose h/help c/config= l/library= d/directory= \\
            format-item= format-album=
    end
    """,
    # Parse the global command-line options supported by Beets to determine
    # whether a (specific or arbitrary) subcommand has been specified.  If the
    # same command-line (up to the subcommand) is seen twice, a cached result
    # is used.
    #
    # If a single argument is provided, the current command-line buffer is
    # checked to contain a beets subcommand of the given name.  Otherwise, the
    # current command-line buffer is checked for any beets subcommand.  If the
    # respective check succeeds, 0 is returned.
    """
    # Test for a (particular) 'beet' subcommand in the command-line buffer.
    function __fish_beet_subcommand
        set -l cmd (commandline -opc)
        set -e cmd[1]
        set -l test_cmd $argv[1]

        set -f cached $__fish_beet_subcommand_cache
        set -l crange "1 .. $(count $cached)"
        if not set -q __fish_beet_subcommand_cache
            or test "$cmd[$crange]" != "$cached"

            argparse --stop-nonopt (__fish_beet_global_optspec) -- $cmd
            or return 1

            set -q _flag_help; and return 1
            test (count $argv) -eq 0; and return 1

            set -l crange "1 .. -$(count $argv)"
            set -g __fish_beet_subcommand_cache $cmd[$crange]
            set -f cached $__fish_beet_subcommand_cache
        end 2>/dev/null

        if test -n "$test_cmd"
            test "$test_cmd" = "$cached[-1]"
        else
            test (count $cached) -gt 0
        end
    end
    """,
    # Determine whether a metadata field-value pair is being filled out, for a
    # particular field name.  This is used for completions in search queries.
    """
    # Test for a '<field>:<value>' argument in the command-line buffer.
    function __fish_beet_metadata_param
        set -l cmd (commandline -ct)
        set -l field (string split -f 1 -- ":" $cmd)
        or return 1

        if test -n "$argv[1]"
            test "$field" = "$argv[1]"
        else
            return 0
        end
    end
    """,
]


def fish_config_dir() -> Path:
    """
    The directory for the user's Fish configuration.
    """

    config_home: Path
    if "XDG_CONFIG_HOME" in os.environ:
        config_home = Path(os.environ["XDG_CONFIG_HOME"])
    else:
        config_home = Path.home() / ".config"

    return config_home / "fish"


# A table of translations to escape strings for Fish.
# See: 'escape_string_script()' on GitHub: 'fish-shell/fish-shell',
#   'src/common.rs', as of '936f7d9b8d3faeb49de4e617d76eaedabce09aaa'.
ESCAPE_SCRIPT_TABLE = str.maketrans(
    {
        "\t": "\\t",
        "\n": "\\n",
        "\b": "\\b",
        "\r": "\\r",
        "\\": "\\\\",
        "\x1b": "\\e",
        "'": "\\'",
        '"': '\\"',
        "\x7f": "\\x7F",
    }
    | {c: f"\\{c}" for c in "&$ #<>()[]{}?*|;%~"}
    | {chr(i): f"\\x{i:02X}" for i in range(26)}
    | {chr(0xF600 + i): f"\\X{i:02X}" for i in range(256)}
)


def fish_escape(text: str, style: str = "script") -> str:
    """
    Escape text akin to Fish's 'string escape' builtin.
    """
    if style == "script":
        return text.translate(ESCAPE_SCRIPT_TABLE)
    elif style == "var":
        # If the last character is not alphanumeric, Fish's implementation inserts an
        # additional underscore at the end; we don't do that here, but Fish's unescape
        # implementation will happily decode our version too.
        return "".join(c if c.isalnum() else f"_{ord(c):02X}" for c in text)
    else:
        raise RuntimeError(f"invalid encoding style '{style}'")


class FishScript(io.StringIO):
    """
    An in-memory text buffer representing a Fish script.

    It provides methods directly representing useful Fish commands, but with
    Pythonic APIs and good typing.
    """

    def __init__(self):
        super().__init__()

    def set_array(self, name: str, values: Iterable[str]):
        """
        Set a variable to the given sequence of strings.
        """
        self.write(f"set {name} {' '.join(map(fish_escape, values))}\n")

    def complete(
        self,
        values: Optional[str] = None,
        conditions: Optional[list[str]] = None,
        long: Optional[str] = None,
        short: Optional[str] = None,
        required: Optional[bool] = None,
        description: Optional[str] = None,
        files: bool = False,
    ):
        """
        Add a generic completion.
        """

        if required is None:
            required = bool(values or files)

        self.write("complete -c beet")
        for condition in conditions or []:
            self.write(f" -n {fish_escape(condition)}")
        if short:
            self.write(f" -s {fish_escape(short)}")
        if long:
            self.write(f" -l {fish_escape(long)}")
        self.write(" -F" if files else " -f")
        if values:
            self.write(f" -a {fish_escape(values)}")
        if description:
            self.write(f" -d {fish_escape(description)}")
        if required:
            self.write(" -r")
        self.write("\n")

    def complete_global(
        self,
        long: Optional[str] = None,
        short: Optional[str] = None,
        values: Optional[str] = None,
        files: bool = False,
        description: Optional[str] = None,
    ):
        """
        Add a completion for a global Beets option.
        """

        self.complete(
            conditions=["not __fish_beet_subcommand"],
            values=values,
            long=long,
            short=short,
            description=description,
            files=files,
        )


class FishPlugin(BeetsPlugin):
    def commands(self) -> list[ui.Subcommand]:
        cmd = ui.Subcommand(
            "fish", help="generate a completion script for the Fish shell"
        )
        cmd.func = self.run

        # TODO: Use '--no-fields' instead of '--noFields'.
        cmd.parser.add_option(
            "-f",
            "--noFields",
            action="store_true",
            default=False,
            help="do not complete the names of metadata fields",
        )

        # TODO: Use '--extra-values' instead of '--extravalues'.
        cmd.parser.add_option(
            "-e",
            "--extravalues",
            action="append",
            type="choice",
            choices=library.Item.all_keys() + library.Album.all_keys(),
            help="complete the known values of the specified metadata fields",
        )

        output_default = str(fish_config_dir() / "completions" / "beet.fish")
        cmd.parser.add_option(
            "-o",
            "--output",
            default=output_default,
            help=f"where the script is saved (default: {output_default})",
        )

        return [cmd]

    def run(
        self,
        lib: library.Library,
        opts: optparse.Values,
        args: list[str],
    ):
        # Get the user-provided options.
        include_fields = not getattr(opts, "noFields")
        extra_comp_fields = cast(list[str], getattr(opts, "extravalues") or [])
        output = Path(getattr(opts, "output"))
        assert len(args) == 0

        # Try to ensure we will be able to write the output file.
        output.parent.mkdir(parents=True, exist_ok=True)

        # Set up an in-memory buffer we will first write everything into.
        script = FishScript()

        # Put the helper items at the top of the script.
        for helper in HELPERS:
            script.write(textwrap.dedent(helper))

        # Prevent arbitrary file completion in 'beet'.
        script.complete(files=False)

        # The commands supported by 'beet', including from plugins.
        commands: list[ui.Subcommand] = [
            *beets.ui.commands.default_commands,
            *beets.ui.commands.plugins.commands(),
        ]

        # Global options supported by 'beet'.
        # TODO: Expose these directly from the 'ui' module and extract them
        #   programmatically from there, as is done for the subcommands.
        script.complete_global(
            "library",
            "l",
            files=True,
            description="the library database file",
        )
        script.complete_global(
            "directory", "d", files=True, description="the music directory"
        )
        script.complete_global(
            "verbose", "v", description="print debugging information"
        )
        script.complete_global("help", "h", description="print a help message")
        script.complete_global(
            "config",
            "c",
            files=True,
            description="the configuration file to use",
        )
        script.complete_global(
            "format-item", description="print with custom format"
        )
        script.complete_global(
            "format-album", description="print with custom format"
        )

        # Add completions for command names.
        for command in commands:
            names = [command.name, *command.aliases]
            names_text = " ".join(fish_escape(n) for n in names)
            not_in_command = "not __fish_beet_subcommand"
            script.complete(
                f"(string split ' ' -- {names_text})",
                conditions=[not_in_command],
                description=command.help,
            )

        if include_fields:
            # The set of fields to provide completions for.
            fields = {
                *library.Item.all_keys(),
                *library.Album.all_keys(),
                *extra_comp_fields,
            }

            # The completions include a ':' as it always follows.
            field_comps = (f"{f}:" for f in fields)
            script.set_array("__fish_beet_flds", field_comps)
            in_command = "__fish_beet_subcommand"
            not_in_value = "not __fish_beet_metadata_param"
            script.complete(
                "$__fish_beet_flds",
                conditions=[in_command, not_in_value],
                description="known metadata field",
            )

        if extra_comp_fields:
            # The set of values for every user-specified extra field.
            extra_values: dict[str, set[str]] = dict.fromkeys(
                extra_comp_fields, set()
            )
            for item in lib.items():
                for key, val in extra_values.items():
                    val.add(str(item[key]))

            for field, values in extra_values.items():
                field_text = fish_escape(field, style="var")
                value_array = f"__fish_beet_field_{field_text}"
                # The field name is explicit since we are adding to the token the user
                # is actively writing to -- usually we only examine the preceding ones.
                script.set_array(value_array, (f"{field}:{v}" for v in values))
                in_command = "__fish_beet_subcommand"
                in_value = f"__fish_beet_metadata_param {fish_escape(field)}"
                script.complete(
                    values=f"${value_array}",
                    conditions=[in_command, in_value],
                    description="known metadata value",
                )

        # Write the buffered text to the file.
        output.write_text(script.getvalue())
