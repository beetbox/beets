# This file is part of beets.
# Copyright 2015, François-Xavier Thomas.
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

"""Use command-line tools to check for audio file corruption.
"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.util import displayable_path
from beets import ui
from subprocess import check_output, CalledProcessError, list2cmdline, STDOUT
import shlex
import os
import errno
import sys


class BadFiles(BeetsPlugin):
    def run_command(self, cmd):
        self._log.debug("running command: {}",
                        displayable_path(list2cmdline(cmd)))
        try:
            output = check_output(cmd, stderr=STDOUT)
            return 0, [line for line in output.split("\n") if line]
        except CalledProcessError as e:
            return 1, [line for line in e.output.split("\n") if line]
        except OSError as e:
            if e.errno == errno.ENOENT:
                ui.print_("command not found: {}".format(cmd[0]))
                sys.exit(1)
            else:
                raise

    def check_mp3val(self, path):
        errors, output = self.run_command(["mp3val", path])
        if errors == 0:
            output = [line for line in output if line.startswith("WARNING:")]
            errors = len(output)
        return errors, output

    def check_flac(self, path):
        return self.run_command(["flac", "-wst", path])

    def check_custom(self, command):
        def checker(path):
            cmd = shlex.split(command)
            cmd.append(path)
            return self.run_command(cmd)
        return checker

    def get_checker(self, ext):
        ext = ext.lower()
        command = self.config['commands'].get().get(ext)
        if command:
            return self.check_custom(command)
        elif ext == "mp3":
            return self.check_mp3val
        elif ext == "flac":
            return self.check_flac

    def check_bad(self, lib, opts, args):
        for item in lib.items(args):

            # First, check whether the path exists. If not, the user
            # should probably run `beet update` to cleanup your library.
            dpath = displayable_path(item.path)
            self._log.debug("checking path: {}", dpath)
            if not os.path.exists(item.path):
                ui.print_("{}: file does not exist".format(dpath))

            # Run the checker against the file if one is found
            ext = os.path.splitext(item.path)[1][1:]
            checker = self.get_checker(ext)
            if not checker:
                continue
            errors, output = checker(item.path)
            if errors == 0:
                ui.print_("{}: ok".format(dpath))
            else:
                ui.print_("{}: checker found {} errors or warnings"
                          .format(dpath, errors))
                for line in output:
                    ui.print_("  {}".format(displayable_path(line)))

    def commands(self):
        bad_command = Subcommand('bad',
                                 help='check for corrupt or missing files')
        bad_command.func = self.check_bad
        return [bad_command]
