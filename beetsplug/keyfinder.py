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

import subprocess

from beets import ui
from beets import util
from beets.plugins import BeetsPlugin


class KeyFinderPlugin(BeetsPlugin):

    def __init__(self):
        super(KeyFinderPlugin, self).__init__()
        self.config.add({
            u'bin': u'KeyFinder',
            u'auto': True,
            u'overwrite': False,
        })
        self.config['auto'].get(bool)
        self._import_stages = [self.imported]

    def commands(self):
        cmd = ui.Subcommand('keyfinder',
                            help='detect and add initial key from audio')
        cmd.func = self.command
        return [cmd]

    def command(self, lib, opts, args):
        self.find_key(lib.items(ui.decargs(args)))

    def imported(self, session, task):
        if self.config['auto'].get(bool):
            self.find_key(task.items)

    def find_key(self, items):
        overwrite = self.config['overwrite'].get(bool)
        bin = util.bytestring_path(self.config['bin'].get(unicode))

        for item in items:
            if item['initial_key'] and not overwrite:
                continue

            try:
                key = util.command_output([bin, '-f', item.path])
            except (subprocess.CalledProcessError, OSError) as exc:
                self._log.error(u'execution failed: {0}', exc)
                continue

            item['initial_key'] = key
            self._log.debug(u'added computed initial key {0} for {1}',
                            key, util.displayable_path(item.path))
            item.try_write()
            item.store()
