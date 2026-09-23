"""The 'config' command: show and edit user configuration."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol

from beets import config, ui
from beets.exceptions import UserError
from beets.util import displayable_path, editor_command, interactive_open

if TYPE_CHECKING:
    from beets.library import Library


class ConfigCLIOpts(Protocol):
    paths: bool | None
    defaults: bool
    edit: bool | None
    redact: bool
    config: str | None


def config_func(lib: Library, opts: ConfigCLIOpts, args: list[str]) -> None:
    # Make sure lazy configuration is loaded
    config.resolve()

    # Print paths.
    if opts.paths:
        filenames = []
        for source in config.sources:
            if not opts.defaults and source.default:
                continue
            if source.filename:
                filenames.append(source.filename)

        # In case the user config file does not exist, prepend it to the
        # list.
        user_path = config.user_config_path()
        if user_path not in filenames:
            filenames.insert(0, user_path)

        for filename in filenames:
            ui.print_(displayable_path(filename))

    # Open in editor.
    elif opts.edit:
        # Note:  This branch *should* be unreachable
        # since the normal flow should be short-circuited
        # by the special case in ui._raw_main
        config_edit(opts)

    # Dump configuration.
    else:
        config_out = config.dump(full=opts.defaults, redact=opts.redact)
        if config_out.strip() != "{}":
            ui.print_(config_out)
        else:
            print("Empty configuration")


def config_edit(cli_options: ConfigCLIOpts) -> None:
    """Open a program to edit the user configuration.
    An empty config file is created if no existing config file exists.
    """
    path = cli_options.config or config.user_config_path()
    editor = editor_command()

    if not editor:
        raise UserError(
            "Please set the VISUAL or EDITOR environment variable to edit"
            " configuration."
        )
    try:
        if not os.path.isfile(path):
            open(path, "w+").close()
        interactive_open([path], editor)
    except FileNotFoundError:
        raise UserError(f"Editor {editor!r} not found.")
    except OSError as exc:
        raise UserError(f"Could not edit configuration: {exc}")


config_cmd = ui.Subcommand("config", help="show or edit the user configuration")
config_cmd.parser.add_option(
    "-p",
    "--paths",
    action="store_true",
    help="show files that configuration was loaded from",
)
config_cmd.parser.add_option(
    "-e",
    "--edit",
    action="store_true",
    help="edit user configuration with $VISUAL (or $EDITOR)",
)
config_cmd.parser.add_option(
    "-d",
    "--defaults",
    action="store_true",
    default=False,
    help="include the default configuration",
)
config_cmd.parser.add_option(
    "-c",
    "--clear",
    action="store_false",
    dest="redact",
    default=True,
    help="do not redact sensitive fields",
)
config_cmd.func = config_func
