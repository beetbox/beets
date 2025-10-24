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

"""This module contains all of the core logic for beets' command-line
interface. To invoke the CLI, just call beets.ui.main(). The actual
CLI commands are implemented in the ui.commands module.
"""

from __future__ import annotations

import errno
import optparse
import os.path
import sqlite3
import sys
import traceback
from typing import TYPE_CHECKING

import confuse

from beets import IncludeLazyConfig, config, library, logging, plugins, util
from beets.dbcore import db
from beets.dbcore import query as db_query
from beets.ui import commands, core
from beets.ui._common import UserError
from beets.ui.colors import color_split, colorize, uncolorize
from beets.ui.core import (
    CommonOptionsParser,
    Subcommand,
    SubcommandsOptionParser,
    _in_encoding,
    _out_encoding,
    get_path_formats,
    get_replacements,
    input_,
    input_options,
    input_select_objects,
    input_yn,
    print_,
    should_move,
    should_write,
    show_model_changes,
    split_into_lines,
)

if TYPE_CHECKING:
    from beets.library.library import Library


# On Windows platforms, use colorama to support "ANSI" terminal colors.
if sys.platform == "win32":
    try:
        import colorama
    except ImportError:
        pass
    else:
        colorama.init()

__all__: list[str] = [
    "CommonOptionsParser",
    "Subcommand",
    "SubcommandsOptionParser",
    "_in_encoding",
    "_out_encoding",
    "UserError",
    "color_split",
    "colorize",
    "commands",
    "core",
    "input_",
    "input_options",
    "input_select_objects",
    "print_",
    "should_write",
    "should_move",
    "show_model_changes",
    "split_into_lines",
    "uncolorize",
]


log: logging.BeetsLogger = logging.getLogger("beets")
if not log.handlers:
    log.addHandler(logging.StreamHandler())
log.propagate = False  # Don't propagate to root handler.


# The main entry point and bootstrapping.


def _setup(
    options: optparse.Values, lib: library.Library | None
) -> tuple[list[Subcommand], library.Library]:
    """Prepare and global state and updates it with command line options.

    Returns a list of subcommands, a list of plugins, and a library instance.
    """
    config: IncludeLazyConfig = _configure(options)

    plugins.load_plugins()

    # Get the default subcommands.
    from beets.ui.commands import default_commands

    subcommands: list[Subcommand] = list(default_commands)
    subcommands.extend(plugins.commands())

    if lib is None:
        lib = _open_library(config)
        _ = plugins.send("library_opened", lib=lib)

    return subcommands, lib


def _configure(options: optparse.Values) -> IncludeLazyConfig:
    """Amend the global configuration object with command line options."""
    # Add any additional config files specified with --config. This
    # special handling lets specified plugins get loaded before we
    # finish parsing the command line.
    if getattr(options, "config", None) is not None:
        overlay_path = options.config
        del options.config
        config.set_file(overlay_path)
    else:
        overlay_path = None
    config.set_args(options)

    # Configure the logger.
    if config["verbose"].get(int):
        log.set_global_level(logging.DEBUG)
    else:
        log.set_global_level(logging.INFO)

    if overlay_path:
        log.debug(
            "overlaying configuration: {}", util.displayable_path(overlay_path)
        )

    config_path = config.user_config_path()
    if os.path.isfile(config_path):
        log.debug("user configuration: {}", util.displayable_path(config_path))
    else:
        log.debug(
            "no user configuration found at {}",
            util.displayable_path(config_path),
        )

    log.debug("data directory: {}", util.displayable_path(config.config_dir()))
    return config


def _ensure_db_directory_exists(path):
    if path == b":memory:":  # in memory db
        return
    newpath = os.path.dirname(path)
    if not os.path.isdir(newpath):
        if input_yn(
            f"The database directory {util.displayable_path(newpath)} does not"
            " exist. Create it (Y/n)?"
        ):
            os.makedirs(newpath)


def _open_library(config: confuse.LazyConfig) -> library.Library:
    """Create a new library instance from the configuration."""
    dbpath = util.bytestring_path(config["library"].as_filename())
    _ensure_db_directory_exists(dbpath)
    try:
        lib = library.Library(
            dbpath,
            config["directory"].as_filename(),
            get_path_formats(),
            get_replacements(),
        )
        lib.get_item(0)  # Test database connection.
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as db_error:
        log.debug("{}", traceback.format_exc())
        raise UserError(
            f"database file {util.displayable_path(dbpath)} cannot not be"
            f" opened: {db_error}"
        )
    log.debug(
        "library database: {}\nlibrary directory: {}",
        util.displayable_path(lib.path),
        util.displayable_path(lib.directory),
    )
    return lib


def _raw_main(args: list[str], lib: Library | None = None) -> None:
    """A helper function for `main` without top-level exception
    handling.
    """
    parser = SubcommandsOptionParser()
    parser.add_format_option(flags=("--format-item",), target=library.Item)
    parser.add_format_option(flags=("--format-album",), target=library.Album)
    _ = parser.add_option(
        "-l", "--library", dest="library", help="library database file to use"
    )
    _ = parser.add_option(
        "-d",
        "--directory",
        dest="directory",
        help="destination music directory",
    )
    _ = parser.add_option(
        "-v",
        "--verbose",
        dest="verbose",
        action="count",
        help="log more details (use twice for even more)",
    )
    _ = parser.add_option(
        "-c", "--config", dest="config", help="path to configuration file"
    )

    def parse_csl_callback(
        option: optparse.Option, _, value: str, parser: SubcommandsOptionParser
    ) -> None:
        """Parse a comma-separated list of values."""
        setattr(
            parser.values,
            option.dest,  # type: ignore[arg-type]
            list(filter(None, value.split(","))),
        )

    parser.add_option(
        "-p",
        "--plugins",
        dest="plugins",
        action="callback",
        callback=parse_csl_callback,
        help="a comma-separated list of plugins to load",
    )
    parser.add_option(
        "-P",
        "--disable-plugins",
        dest="disabled_plugins",
        action="callback",
        callback=parse_csl_callback,
        help="a comma-separated list of plugins to disable",
    )
    parser.add_option(
        "-h",
        "--help",
        dest="help",
        action="store_true",
        help="show this help message and exit",
    )
    parser.add_option(
        "--version",
        dest="version",
        action="store_true",
        help=optparse.SUPPRESS_HELP,
    )

    options, subargs = parser.parse_global_options(args)

    # Special case for the `config --edit` command: bypass _setup so
    # that an invalid configuration does not prevent the editor from
    # starting.
    if (
        subargs
        and subargs[0] == "config"
        and ("-e" in subargs or "--edit" in subargs)
    ):
        from beets.ui.commands import config_edit

        return config_edit()

    test_lib = bool(lib)
    subcommands, lib = _setup(options, lib)
    parser.add_subcommand(*subcommands)

    subcommand, suboptions, subargs = parser.parse_subcommand(subargs)
    subcommand.func(lib, suboptions, subargs)

    plugins.send("cli_exit", lib=lib)
    if not test_lib:
        # Clean up the library unless it came from the test harness.
        lib._close()


def main(args: list[str] | None = None) -> None:
    """Run the main command-line interface for beets. Includes top-level
    exception handlers that print friendly error messages.
    """
    if "AppData\\Local\\Microsoft\\WindowsApps" in sys.exec_prefix:
        log.error(
            "error: beets is unable to use the Microsoft Store version of "
            "Python. Please install Python from https://python.org.\n"
            "error: More details can be found here "
            "https://beets.readthedocs.io/en/stable/guides/main.html"
        )
        sys.exit(1)
    try:
        _raw_main(args or [])
    except UserError as exc:
        message = exc.args[0] if exc.args else None
        log.error("error: {}", message)
        sys.exit(1)
    except util.HumanReadableError as exc:
        exc.log(log)
        sys.exit(1)
    except library.FileOperationError as exc:
        # These errors have reasonable human-readable descriptions, but
        # we still want to log their tracebacks for debugging.
        log.debug("{}", traceback.format_exc())
        log.error("{}", exc)
        sys.exit(1)
    except confuse.ConfigError as exc:
        log.error("configuration error: {}", exc)
        sys.exit(1)
    except db_query.InvalidQueryError as exc:
        log.error("invalid query: {}", exc)
        sys.exit(1)
    except OSError as exc:
        if exc.errno == errno.EPIPE:
            # "Broken pipe". End silently.
            sys.stderr.close()
        else:
            raise
    except KeyboardInterrupt:
        # Silently ignore ^C except in verbose mode.
        log.debug("{}", traceback.format_exc())
    except db.DBAccessError as exc:
        log.error(
            "database access error: {}\n"
            "the library file might have a permissions problem",
            exc,
        )
        sys.exit(1)
