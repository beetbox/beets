"""The `import` command: import new music into the library."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from beets import config, logging, plugins
from beets.ui._common import UserError
from beets.ui.core import Subcommand, _store_dict
from beets.util import displayable_path, normpath, syspath

from .._utils import parse_logfiles
from .session import TerminalImportSession

if TYPE_CHECKING:
    from logging import FileHandler
    from optparse import Values

    from beets.dbcore import Query
    from beets.library import Library


# Global logger.
log = logging.getLogger("beets")


def import_files(
    lib: Library,
    paths: list[bytes],
    query: Query | str | list[str] | tuple[str] | None,
) -> None:
    """Import the files in the given list of paths or matching the
    query.
    """
    # Check parameter consistency.
    if config["import"]["quiet"] and config["import"]["timid"]:
        raise UserError("can't be both quiet and timid")

    # Open the log.
    if config["import"]["log"].get() is not None:
        logpath: str = syspath(config["import"]["log"].as_filename())
        loghandler: FileHandler | None
        try:
            loghandler = logging.FileHandler(logpath, encoding="utf-8")
        except OSError:
            raise UserError(
                "Could not open log file for writing:"
                f" {displayable_path(logpath)}"
            )
    else:
        loghandler = None

    # Never ask for input in quiet mode.
    if config["import"]["resume"].get() == "ask" and config["import"]["quiet"]:
        config["import"]["resume"] = False

    session: TerminalImportSession = TerminalImportSession(
        lib, loghandler, paths, query
    )
    session.run()

    # Emit event.
    _ = plugins.send("import", lib=lib, paths=paths)


def import_func(
    lib: Library,
    opts: Values,
    args: list[str] | tuple[str],
) -> None:
    config["import"].set_args(opts)

    # Special case: --copy flag suppresses import_move (which would
    # otherwise take precedence).
    if opts.copy:
        config["import"]["move"] = False

    query: Query | str | list[str] | tuple[str] | None
    byte_paths: list[bytes]
    if opts.library:
        query = args
        byte_paths = []
    else:
        query = None
        paths: list[str] | tuple[str] = args

        # The paths from the logfiles go into a separate list to allow handling
        # errors differently from user-specified paths.
        paths_from_logfiles: list[str] = list(
            parse_logfiles(opts.from_logfiles or [])
        )

        if not paths and not paths_from_logfiles:
            raise UserError("no path specified")

        byte_paths = [os.fsencode(p) for p in paths]
        byte_paths_from_logfiles: list[bytes] = [
            os.fsencode(p) for p in paths_from_logfiles
        ]

        # Check the user-specified directories.
        path: bytes
        for path in byte_paths:
            if not os.path.exists(syspath(normpath(path))):
                raise UserError(
                    f"no such file or directory: {displayable_path(path)}"
                )

        # Check the directories from the logfiles, but don't throw an error in
        # case those paths don't exist. Maybe some of those paths have already
        # been imported and moved separately, so logging a warning should
        # suffice.
        for path in byte_paths_from_logfiles:
            if not os.path.exists(syspath(normpath(path))):
                log.warning(
                    "No such file or directory: {}", displayable_path(path)
                )
                continue

            byte_paths.append(path)

        # If all paths were read from a logfile, and none of them exist, throw
        # an error
        if not paths:
            raise UserError("none of the paths are importable")

    import_files(lib, byte_paths, query)


import_cmd = Subcommand(
    "import", help="import new music", aliases=("imp", "im")
)
_ = import_cmd.parser.add_option(
    "-c",
    "--copy",
    action="store_true",
    default=None,
    help="copy tracks into library directory (default)",
)
_ = import_cmd.parser.add_option(
    "-C",
    "--nocopy",
    action="store_false",
    dest="copy",
    help="don't copy tracks (opposite of -c)",
)
_ = import_cmd.parser.add_option(
    "-m",
    "--move",
    action="store_true",
    dest="move",
    help="move tracks into the library (overrides -c)",
)
_ = import_cmd.parser.add_option(
    "-w",
    "--write",
    action="store_true",
    default=None,
    help="write new metadata to files' tags (default)",
)
_ = import_cmd.parser.add_option(
    "-W",
    "--nowrite",
    action="store_false",
    dest="write",
    help="don't write metadata (opposite of -w)",
)
_ = import_cmd.parser.add_option(
    "-a",
    "--autotag",
    action="store_true",
    dest="autotag",
    help="infer tags for imported files (default)",
)
_ = import_cmd.parser.add_option(
    "-A",
    "--noautotag",
    action="store_false",
    dest="autotag",
    help="don't infer tags for imported files (opposite of -a)",
)
_ = import_cmd.parser.add_option(
    "-p",
    "--resume",
    action="store_true",
    default=None,
    help="resume importing if interrupted",
)
_ = import_cmd.parser.add_option(
    "-P",
    "--noresume",
    action="store_false",
    dest="resume",
    help="do not try to resume importing",
)
_ = import_cmd.parser.add_option(
    "-q",
    "--quiet",
    action="store_true",
    dest="quiet",
    help="never prompt for input: skip albums instead",
)
_ = import_cmd.parser.add_option(
    "--quiet-fallback",
    type="string",
    dest="quiet_fallback",
    help="decision in quiet mode when no strong match: skip or asis",
)
_ = import_cmd.parser.add_option(
    "-l",
    "--log",
    dest="log",
    help="file to log untaggable albums for later review",
)
_ = import_cmd.parser.add_option(
    "-s",
    "--singletons",
    action="store_true",
    help="import individual tracks instead of full albums",
)
_ = import_cmd.parser.add_option(
    "-t",
    "--timid",
    dest="timid",
    action="store_true",
    help="always confirm all actions",
)
_ = import_cmd.parser.add_option(
    "-L",
    "--library",
    dest="library",
    action="store_true",
    help="retag items matching a query",
)
_ = import_cmd.parser.add_option(
    "-i",
    "--incremental",
    dest="incremental",
    action="store_true",
    help="skip already-imported directories",
)
_ = import_cmd.parser.add_option(
    "-I",
    "--noincremental",
    dest="incremental",
    action="store_false",
    help="do not skip already-imported directories",
)
_ = import_cmd.parser.add_option(
    "-R",
    "--incremental-skip-later",
    action="store_true",
    dest="incremental_skip_later",
    help="do not record skipped files during incremental import",
)
_ = import_cmd.parser.add_option(
    "-r",
    "--noincremental-skip-later",
    action="store_false",
    dest="incremental_skip_later",
    help="record skipped files during incremental import",
)
_ = import_cmd.parser.add_option(
    "--from-scratch",
    dest="from_scratch",
    action="store_true",
    help="erase existing metadata before applying new metadata",
)
_ = import_cmd.parser.add_option(
    "--flat",
    dest="flat",
    action="store_true",
    help="import an entire tree as a single album",
)
_ = import_cmd.parser.add_option(
    "-g",
    "--group-albums",
    dest="group_albums",
    action="store_true",
    help="group tracks in a folder into separate albums",
)
_ = import_cmd.parser.add_option(
    "--pretend",
    dest="pretend",
    action="store_true",
    help="just print the files to import",
)
_ = import_cmd.parser.add_option(
    "-S",
    "--search-id",
    dest="search_ids",
    action="append",
    metavar="ID",
    help="restrict matching to a specific metadata backend ID",
)
_ = import_cmd.parser.add_option(
    "--from-logfile",
    dest="from_logfiles",
    action="append",
    metavar="PATH",
    help="read skipped paths from an existing logfile",
)
_ = import_cmd.parser.add_option(
    "--set",
    dest="set_fields",
    action="callback",
    callback=_store_dict,
    metavar="FIELD=VALUE",
    help="set the given fields to the supplied values",
)
import_cmd.func = import_func
