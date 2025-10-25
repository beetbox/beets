"""The 'completion' command: print shell script for command line completion."""

import os
import re

from beets import library, logging, plugins, ui
from beets.util import syspath

# Global logger.
log = logging.getLogger("beets")


def print_completion(*args):
    from beets.ui.commands import default_commands

    for line in completion_script(default_commands + plugins.commands()):
        ui.print_(line, end="")
    if not any(os.path.isfile(syspath(p)) for p in BASH_COMPLETION_PATHS):
        log.warning(
            "Warning: Unable to find the bash-completion package. "
            "Command line completion might not work."
        )


completion_cmd = ui.Subcommand(
    "completion",
    help="print shell script that provides command line completion",
)
completion_cmd.func = print_completion
completion_cmd.hide = True


BASH_COMPLETION_PATHS = [
    b"/etc/bash_completion",
    b"/usr/share/bash-completion/bash_completion",
    b"/usr/local/share/bash-completion/bash_completion",
    # SmartOS
    b"/opt/local/share/bash-completion/bash_completion",
    # Homebrew (before bash-completion2)
    b"/usr/local/etc/bash_completion",
]


def completion_script(commands):
    """Yield the full completion shell script as strings.

    ``commands`` is alist of ``ui.Subcommand`` instances to generate
    completion data for.
    """
    base_script = os.path.join(
        os.path.dirname(__file__), "../completion_base.sh"
    )
    with open(base_script) as base_script:
        yield base_script.read()

    options = {}
    aliases = {}
    command_names = []

    # Collect subcommands
    for cmd in commands:
        name = cmd.name
        command_names.append(name)

        for alias in cmd.aliases:
            if re.match(r"^\w+$", alias):
                aliases[alias] = name

        options[name] = {"flags": [], "opts": []}
        for opts in cmd.parser._get_all_options()[1:]:
            if opts.action in ("store_true", "store_false"):
                option_type = "flags"
            else:
                option_type = "opts"

            options[name][option_type].extend(
                opts._short_opts + opts._long_opts
            )

    # Add global options
    options["_global"] = {
        "flags": ["-v", "--verbose"],
        "opts": "-l --library -c --config -d --directory -h --help".split(" "),
    }

    # Add flags common to all commands
    options["_common"] = {"flags": ["-h", "--help"]}

    # Start generating the script
    yield "_beet() {\n"

    # Command names
    yield f"  local commands={' '.join(command_names)!r}\n"
    yield "\n"

    # Command aliases
    yield f"  local aliases={' '.join(aliases.keys())!r}\n"
    for alias, cmd in aliases.items():
        yield f"  local alias__{alias.replace('-', '_')}={cmd}\n"
    yield "\n"

    # Fields
    fields = library.Item._fields.keys() | library.Album._fields.keys()
    yield f"  fields={' '.join(fields)!r}\n"

    # Command options
    for cmd, opts in options.items():
        for option_type, option_list in opts.items():
            if option_list:
                option_list = " ".join(option_list)
                yield (
                    "  local"
                    f" {option_type}__{cmd.replace('-', '_')}='{option_list}'\n"
                )

    yield "  _beet_dispatch\n"
    yield "}\n"
