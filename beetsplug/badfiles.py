# -*- coding: utf-8 -*-
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

"""Use command-line tools to check for audio file corruption.
"""

from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.util import displayable_path, confit
from beets import ui
from subprocess import check_output, CalledProcessError, list2cmdline, STDOUT
import shlex
import os
import errno
import sys
import six


class BadFiles(BeetsPlugin):
    def run_command(self, cmd):
        self._log.debug(u"running command: {}",
                        displayable_path(list2cmdline(cmd)))
        try:
            output = check_output(cmd, stderr=STDOUT)
            errors = 0
            status = 0
        except CalledProcessError as e:
            output = e.output
            errors = 1
            status = e.returncode
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise ui.UserError(u"command not found: {}".format(cmd[0]))
            else:
                raise ui.UserError(
                    u"error invoking {}: {}".format(cmd[0], e)
                )
        output = output.decode(sys.getfilesystemencoding())
        return status, errors, [line for line in output.split("\n") if line]

    def check_mp3val(self, path):
        status, errors, output = self.run_command(["mp3val", path])
        if status == 0:
            output = [line for line in output if line.startswith("WARNING:")]
            errors = len(output)
        return status, errors, output

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
        try:
            command = self.config['commands'].get(dict).get(ext)
        except confit.NotFoundError:
            command = None
        if command:
            return self.check_custom(command)
        elif ext == "mp3":
            return self.check_mp3val
        elif ext == "flac":
            return self.check_flac

    def check_bad(self, lib, opts, args):
        for item in lib.items(ui.decargs(args)):

            # First, check whether the path exists. If not, the user
            # should probably run `beet update` to cleanup your library.
            dpath = displayable_path(item.path)
            self._log.debug(u"checking path: {}", dpath)
            if not os.path.exists(item.path):
                ui.print_(u"{}: file does not exist".format(
                    ui.colorize('text_error', dpath)))

            # Run the checker against the file if one is found
            ext = os.path.splitext(item.path)[1][1:].decode('utf8', 'ignore')
            checker = self.get_checker(ext)
            if not checker:
                self._log.debug(u"no checker available for {}", ext)
                continue
            path = item.path
            if not isinstance(path, six.text_type):
                path = item.path.decode(sys.getfilesystemencoding())
            status, errors, output = checker(path)
            if status > 0:
                ui.print_(u"{}: checker exited withs status {}"
                          .format(ui.colorize('text_error', dpath), status))
                for line in output:
                    ui.print_(u"  {}".format(displayable_path(line)))
            elif errors > 0:
                ui.print_(u"{}: checker found {} errors or warnings"
                          .format(ui.colorize('text_warning', dpath), errors))
                for line in output:
                    ui.print_(u"  {}".format(displayable_path(line)))
            elif opts.verbose:
                ui.print_(u"{}: ok".format(ui.colorize('text_success', dpath)))

    def commands(self):
        bad_command = Subcommand('bad',
                                 help=u'check for corrupt or missing files')
        bad_command.parser.add_option(
            u'-v', u'--verbose',
            action='store_true', default=False, dest='verbose',
            help=u'view results for both the bad and uncorrupted files'
        )
        bad_command.func = self.check_bad
        return [bad_command]
