# This file is part of beets.
# Copyright 2015, Thomas Scholtes.
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

"""Uses the `KeyFinder` program to add the `initial_key` field.
"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import subprocess

from beets import ui
from beets import util
from beets.plugins import BeetsPlugin
from beets import config


class KeyFinderPlugin(BeetsPlugin):

    def __init__(self):
        super(KeyFinderPlugin, self).__init__()
        self.config.add({
            u'bin': u'KeyFinder',
            u'auto': True,
            u'overwrite': False,
        })

        if self.config['auto'].get(bool):
            self.import_stages = [self.imported]

    def commands(self):
        cmd = ui.Subcommand('keyfinder',
                            help='detect and add initial key from audio')
        cmd.func = self.command
        return [cmd]

    def command(self, lib, opts, args):
        self.find_key(lib.items(ui.decargs(args)),
                      write=config['import']['write'].get(bool))

    def imported(self, session, task):
        self.find_key(task.items)

    def find_key(self, items, write=False):
        overwrite = self.config['overwrite'].get(bool)
        bin = util.bytestring_path(self.config['bin'].get(unicode))

        for item in items:
            if item['initial_key'] and not overwrite:
                continue

            try:
                output = util.command_output([bin, '-f', item.path])
            except (subprocess.CalledProcessError, OSError) as exc:
                self._log.error(u'execution failed: {0}', exc)
                continue

            key_raw = output.rsplit(None, 1)[-1]
            try:
                key = key_raw.decode('utf8')
            except UnicodeDecodeError:
                self._log.error(u'output is invalid UTF-8')
                continue

            item['initial_key'] = key
            self._log.info(u'added computed initial key {0} for {1}',
                           key, util.displayable_path(item.path))

            if write:
                item.try_write()
            item.store()
