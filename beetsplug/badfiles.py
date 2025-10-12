# This file is part of beets.
# Copyright 2016, François-Xavier Thomas.
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

"""Use command-line tools to check for audio file corruption."""

import concurrent.futures
import errno
import os
import shlex
import sys
from subprocess import STDOUT, CalledProcessError, check_output, list2cmdline
from typing import Callable, Optional, Union

import confuse

from beets import importer, library, ui
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.util import displayable_path


class CheckerCommandError(Exception):
    """Raised when running a checker failed.

    Attributes:
        checker: Checker command name.
        path: Path to the file being validated.
        errno: Error number from the checker execution error.
        msg: Message from the checker execution error.
    """

    def __init__(self, cmd, oserror):
        self.checker = cmd[0]
        self.path = cmd[-1]
        self.errno = oserror.errno
        self.msg = str(oserror)


# CheckResult is a tuple of 1. status code, 2. how many errors there were, and 3.
# a list of error output messages.
CheckResult = tuple[int, int, list[str]]

CheckMethod = Callable[[str], CheckResult]


class BadFiles(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.verbose = False

        self.register_listener("import_task_start", self.on_import_task_start)
        self.register_listener(
            "import_task_before_choice", self.on_import_task_before_choice
        )

    def run_command(self, cmd: list[str]) -> CheckResult:
        self._log.debug(
            "running command: {}", displayable_path(list2cmdline(cmd))
        )
        try:
            output: bytes = check_output(cmd, stderr=STDOUT)
            errors = 0
            status = 0
        except CalledProcessError as e:
            output = e.output
            errors = 1
            status = e.returncode
        except OSError as e:
            raise CheckerCommandError(cmd, e)
        output_dec = output.decode(sys.getdefaultencoding(), "replace")
        return status, errors, [line for line in output_dec.split("\n") if line]

    def check_mp3val(self, path: str) -> CheckResult:
        status, errors, output = self.run_command(["mp3val", path])
        if status == 0:
            output = [line for line in output if line.startswith("WARNING:")]
            errors = len(output)
        return status, errors, output

    def check_flac(self, path: str) -> CheckResult:
        return self.run_command(["flac", "-wst", path])

    def check_custom(self, command: str) -> Callable[[str], CheckResult]:
        def checker(path):
            cmd = shlex.split(command)
            cmd.append(path)
            return self.run_command(cmd)

        return checker

    def get_checker(self, ext: str) -> Optional[CheckMethod]:
        ext = ext.lower()
        try:
            command = self.config["commands"].get(dict).get(ext)
        except confuse.NotFoundError:
            command = None
        if command:
            return self.check_custom(command)
        if ext == "mp3":
            return self.check_mp3val
        if ext == "flac":
            return self.check_flac
        return None

    def check_item(self, item: library.Item) -> tuple[bool, list[str]]:
        # First, check whether the path exists. If not, the user
        # should probably run `beet update` to cleanup your library.
        dpath = displayable_path(item.path)
        self._log.debug("checking path: {}", dpath)
        if not os.path.exists(item.path):
            ui.print_(
                f"{ui.colorize('text_error', dpath)}: file does not exist"
            )

        # Run the checker against the file if one is found
        ext = os.path.splitext(item.path)[1][1:].decode("utf8", "ignore")
        checker = self.get_checker(ext)
        if not checker:
            self._log.error("no checker specified in the config for {}", ext)
            return False, []
        path: Union[bytes, str] = item.path
        if not isinstance(path, str):
            path = item.path.decode(sys.getfilesystemencoding())
        try:
            status, errors, output = checker(path)
        except CheckerCommandError as e:
            if e.errno == errno.ENOENT:
                self._log.error(
                    "command not found: {0.checker} when validating file: {0.path}",
                    e,
                )
            else:
                self._log.error("error invoking {0.checker}: {0.msg}", e)
            return False, []

        success = True
        error_lines = []

        if status > 0:
            success = False
            error_lines.append(
                f"{ui.colorize('text_error', dpath)}: checker exited with"
                f" status {status}"
            )
            for line in output:
                error_lines.append(f"  {line}")

        elif errors > 0:
            success = False
            error_lines.append(
                f"{ui.colorize('text_warning', dpath)}: checker found"
                f" {status} errors or warnings"
            )
            for line in output:
                error_lines.append(f"  {line}")
        elif self.verbose:
            error_lines.append(f"{ui.colorize('text_success', dpath)}: ok")

        return success, error_lines

    def on_import_task_start(self, task, session) -> None:
        if not self.config["check_on_import"].get(False):
            return

        checks_failed = []

        for item in task.items:
            _, error_lines = self.check_item(item)
            checks_failed.append(error_lines)

        if checks_failed:
            task._badfiles_checks_failed = checks_failed

    def on_import_task_before_choice(
        self, task, session
    ) -> Optional[importer.Action]:
        if hasattr(task, "_badfiles_checks_failed"):
            ui.print_(
                f"{ui.colorize('text_warning', 'BAD')} one or more files failed"
                " checks:"
            )
            for error in task._badfiles_checks_failed:
                for error_line in error:
                    ui.print_(error_line)

            ui.print_()
            ui.print_("What would you like to do?")

            sel = ui.input_options(["aBort", "skip", "continue"])

            if sel == "s":
                return importer.Action.SKIP
            elif sel == "c":
                return None
            elif sel == "b":
                raise importer.ImportAbortError()
            else:
                raise Exception(f"Unexpected selection: {sel}")

        return None

    def command(self, lib, opts, args) -> None:
        # Get items from arguments
        items = lib.items(args)
        self.verbose = opts.verbose

        def check_and_print(item):
            success, error_lines = self.check_item(item)
            if not success:
                for line in error_lines:
                    ui.print_(line)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            for _ in ui.iprogress_bar(
                executor.map(check_and_print, items),
                desc="Checking",
                unit="item",
                total=len(items),
            ):
                pass

    def commands(self):
        bad_command = Subcommand(
            "bad", help="check for corrupt or missing files"
        )
        bad_command.parser.add_option(
            "-v",
            "--verbose",
            action="store_true",
            default=False,
            dest="verbose",
            help="view results for both the bad and uncorrupted files",
        )
        bad_command.func = self.command
        return [bad_command]
