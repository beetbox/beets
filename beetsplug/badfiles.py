#!/usr/bin/python
# coding=utf-8

# Base Python File (badfiles.py)
# Created: Tue 11 Aug 2015 10:46:34 PM CEST
# Version: 1.0
#
# This Python script was developped by François-Xavier Thomas.
# You are free to copy, adapt or modify it.
# If you do so, however, leave my name somewhere in the credits, I'd appreciate it ;)
#
# (ɔ) François-Xavier Thomas <fx.thomas@gmail.com>

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
        self._log.debug(u"running command: %s" % displayable_path(list2cmdline(cmd)))
        try:
            output = check_output(cmd, stderr=STDOUT)
            return 0, [line for line in output.split("\n") if line]
        except CalledProcessError as e:
            return 1, [line for line in e.output.split("\n") if line]
        except OSError as e:
            if e.errno == errno.ENOENT:
                ui.print_("Command '%s' does not exit. Is it installed?" % cmd[0])
                sys.exit(1)
            else:
                raise

    def check_mp3val(self, path):
        errors, output = self.run_command(["mp3val", path])
        if errors == 0:
            output = [line for line in output if line.startswith("WARNING:")]
            errors = sum(1 for line in output if line.startswith("WARNING:"))
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

            # First check if the path exists. If not, should run 'beets update'
            # to cleanup your library.
            dpath = displayable_path(item.path)
            self._log.debug(u"checking path: %s" % dpath)
            if not os.path.exists(item.path):
                ui.print_(u"%s: file does not exist" % dpath)

            # Run the checker against the file if one is found
            ext = os.path.splitext(item.path)[1][1:]
            checker = self.get_checker(ext)
            if not checker:
                continue
            errors, output = checker(item.path)
            if errors == 0:
                ui.print_(u"%s: ok" % dpath)
            else:
                ui.print_(u"%s: checker found %d errors or warnings" % (dpath, errors))
                for line in output:
                    ui.print_(u"  %s" % displayable_path(line))

    def commands(self):
        bad_command = Subcommand('bad', help='check for corrupt or missing files')
        bad_command.func = self.check_bad
        return [bad_command]
