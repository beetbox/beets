"""The `import` command: import new music into the library."""

import os

from beets import config, logging, plugins, ui
from beets.util import displayable_path, normpath, syspath

from .session import TerminalImportSession

# Global logger.
log = logging.getLogger("beets")


def paths_from_logfile(path):
    """Parse the logfile and yield skipped paths to pass to the `import`
    command.
    """
    with open(path, encoding="utf-8") as fp:
        for i, line in enumerate(fp, start=1):
            verb, sep, paths = line.rstrip("\n").partition(" ")
            if not sep:
                raise ValueError(f"line {i} is invalid")

            # Ignore informational lines that don't need to be re-imported.
            if verb in {"import", "duplicate-keep", "duplicate-replace"}:
                continue

            if verb not in {"asis", "skip", "duplicate-skip"}:
                raise ValueError(f"line {i} contains unknown verb {verb}")

            yield os.path.commonpath(paths.split("; "))


def parse_logfiles(logfiles):
    """Parse all `logfiles` and yield paths from it."""
    for logfile in logfiles:
        try:
            yield from paths_from_logfile(syspath(normpath(logfile)))
        except ValueError as err:
            raise ui.UserError(
                f"malformed logfile {displayable_path(logfile)}: {err}"
            ) from err
        except OSError as err:
            raise ui.UserError(
                f"unreadable logfile {displayable_path(logfile)}: {err}"
            ) from err


def import_files(lib, paths: list[bytes], query):
    """Import the files in the given list of paths or matching the
    query.
    """
    # Check parameter consistency.
    if config["import"]["quiet"] and config["import"]["timid"]:
        raise ui.UserError("can't be both quiet and timid")

    # Open the log.
    if config["import"]["log"].get() is not None:
        logpath = syspath(config["import"]["log"].as_filename())
        try:
            loghandler = logging.FileHandler(logpath, encoding="utf-8")
        except OSError:
            raise ui.UserError(
                "Could not open log file for writing:"
                f" {displayable_path(logpath)}"
            )
    else:
        loghandler = None

    # Never ask for input in quiet mode.
    if config["import"]["resume"].get() == "ask" and config["import"]["quiet"]:
        config["import"]["resume"] = False

    session = TerminalImportSession(lib, loghandler, paths, query)
    session.run()

    # Emit event.
    plugins.send("import", lib=lib, paths=paths)


def import_func(lib, opts, args: list[str]):
    config["import"].set_args(opts)

    # Special case: --copy flag suppresses import_move (which would
    # otherwise take precedence).
    if opts.copy:
        config["import"]["move"] = False

    if opts.library:
        query = args
        byte_paths = []
    else:
        query = None
        paths = args

        # The paths from the logfiles go into a separate list to allow handling
        # errors differently from user-specified paths.
        paths_from_logfiles = list(parse_logfiles(opts.from_logfiles or []))

        if not paths and not paths_from_logfiles:
            raise ui.UserError("no path specified")

        byte_paths = [os.fsencode(p) for p in paths]
        paths_from_logfiles = [os.fsencode(p) for p in paths_from_logfiles]

        # Check the user-specified directories.
        for path in byte_paths:
            if not os.path.exists(syspath(normpath(path))):
                raise ui.UserError(
                    f"no such file or directory: {displayable_path(path)}"
                )

        # Check the directories from the logfiles, but don't throw an error in
        # case those paths don't exist. Maybe some of those paths have already
        # been imported and moved separately, so logging a warning should
        # suffice.
        for path in paths_from_logfiles:
            if not os.path.exists(syspath(normpath(path))):
                log.warning(
                    "No such file or directory: {}", displayable_path(path)
                )
                continue

            byte_paths.append(path)

        # If all paths were read from a logfile, and none of them exist, throw
        # an error
        if not byte_paths:
            raise ui.UserError("none of the paths are importable")

    import_files(lib, byte_paths, query)


def _store_dict(option, opt_str, value, parser):
    """Custom action callback to parse options which have ``key=value``
    pairs as values. All such pairs passed for this option are
    aggregated into a dictionary.
    """
    dest = option.dest
    option_values = getattr(parser.values, dest, None)

    if option_values is None:
        # This is the first supplied ``key=value`` pair of option.
        # Initialize empty dictionary and get a reference to it.
        setattr(parser.values, dest, {})
        option_values = getattr(parser.values, dest)

    try:
        key, value = value.split("=", 1)
        if not (key and value):
            raise ValueError
    except ValueError:
        raise ui.UserError(
            f"supplied argument `{value}' is not of the form `key=value'"
        )

    option_values[key] = value


import_cmd = ui.Subcommand(
    "import", help="import new music", aliases=("imp", "im")
)
import_cmd.parser.add_option(
    "-c",
    "--copy",
    action="store_true",
    default=None,
    help="copy tracks into library directory (default)",
)
import_cmd.parser.add_option(
    "-C",
    "--nocopy",
    action="store_false",
    dest="copy",
    help="don't copy tracks (opposite of -c)",
)
import_cmd.parser.add_option(
    "-m",
    "--move",
    action="store_true",
    dest="move",
    help="move tracks into the library (overrides -c)",
)
import_cmd.parser.add_option(
    "-w",
    "--write",
    action="store_true",
    default=None,
    help="write new metadata to files' tags (default)",
)
import_cmd.parser.add_option(
    "-W",
    "--nowrite",
    action="store_false",
    dest="write",
    help="don't write metadata (opposite of -w)",
)
import_cmd.parser.add_option(
    "-a",
    "--autotag",
    action="store_true",
    dest="autotag",
    help="infer tags for imported files (default)",
)
import_cmd.parser.add_option(
    "-A",
    "--noautotag",
    action="store_false",
    dest="autotag",
    help="don't infer tags for imported files (opposite of -a)",
)
import_cmd.parser.add_option(
    "-p",
    "--resume",
    action="store_true",
    default=None,
    help="resume importing if interrupted",
)
import_cmd.parser.add_option(
    "-P",
    "--noresume",
    action="store_false",
    dest="resume",
    help="do not try to resume importing",
)
import_cmd.parser.add_option(
    "-q",
    "--quiet",
    action="store_true",
    dest="quiet",
    help="never prompt for input: skip albums instead",
)
import_cmd.parser.add_option(
    "--quiet-fallback",
    type="string",
    dest="quiet_fallback",
    help="decision in quiet mode when no strong match: skip or asis",
)
import_cmd.parser.add_option(
    "-l",
    "--log",
    dest="log",
    help="file to log untaggable albums for later review",
)
import_cmd.parser.add_option(
    "-s",
    "--singletons",
    action="store_true",
    help="import individual tracks instead of full albums",
)
import_cmd.parser.add_option(
    "-t",
    "--timid",
    dest="timid",
    action="store_true",
    help="always confirm all actions",
)
import_cmd.parser.add_option(
    "-L",
    "--library",
    dest="library",
    action="store_true",
    help="retag items matching a query",
)
import_cmd.parser.add_option(
    "-i",
    "--incremental",
    dest="incremental",
    action="store_true",
    help="skip already-imported directories",
)
import_cmd.parser.add_option(
    "-I",
    "--noincremental",
    dest="incremental",
    action="store_false",
    help="do not skip already-imported directories",
)
import_cmd.parser.add_option(
    "-R",
    "--incremental-skip-later",
    action="store_true",
    dest="incremental_skip_later",
    help="do not record skipped files during incremental import",
)
import_cmd.parser.add_option(
    "-r",
    "--noincremental-skip-later",
    action="store_false",
    dest="incremental_skip_later",
    help="record skipped files during incremental import",
)
import_cmd.parser.add_option(
    "--from-scratch",
    dest="from_scratch",
    action="store_true",
    help="erase existing metadata before applying new metadata",
)
import_cmd.parser.add_option(
    "--flat",
    dest="flat",
    action="store_true",
    help="import an entire tree as a single album",
)
import_cmd.parser.add_option(
    "-g",
    "--group-albums",
    dest="group_albums",
    action="store_true",
    help="group tracks in a folder into separate albums",
)
import_cmd.parser.add_option(
    "--pretend",
    dest="pretend",
    action="store_true",
    help="just print the files to import",
)
import_cmd.parser.add_option(
    "-S",
    "--search-id",
    dest="search_ids",
    action="append",
    metavar="ID",
    help="restrict matching to a specific metadata backend ID",
)
import_cmd.parser.add_option(
    "--from-logfile",
    dest="from_logfiles",
    action="append",
    metavar="PATH",
    help="read skipped paths from an existing logfile",
)
import_cmd.parser.add_option(
    "--set",
    dest="set_fields",
    action="callback",
    callback=_store_dict,
    metavar="FIELD=VALUE",
    help="set the given fields to the supplied values",
)
import_cmd.func = import_func
