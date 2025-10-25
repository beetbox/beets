"""The 'config' command: show and edit user configuration."""

import os

from beets import config, ui, util


def config_func(lib, opts, args):
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
            ui.print_(util.displayable_path(filename))

    # Open in editor.
    elif opts.edit:
        config_edit()

    # Dump configuration.
    else:
        config_out = config.dump(full=opts.defaults, redact=opts.redact)
        if config_out.strip() != "{}":
            ui.print_(config_out)
        else:
            print("Empty configuration")


def config_edit():
    """Open a program to edit the user configuration.
    An empty config file is created if no existing config file exists.
    """
    path = config.user_config_path()
    editor = util.editor_command()
    try:
        if not os.path.isfile(path):
            open(path, "w+").close()
        util.interactive_open([path], editor)
    except OSError as exc:
        message = f"Could not edit configuration: {exc}"
        if not editor:
            message += (
                ". Please set the VISUAL (or EDITOR) environment variable"
            )
        raise ui.UserError(message)


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
