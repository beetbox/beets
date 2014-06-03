# This file is part of beets.
# Copyright 2014, Thomas Scholtes.
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

import logging
import subprocess

from beets import ui
from beets import util
from beets.plugins import BeetsPlugin


log = logging.getLogger('beets')


class KeyFinderPlugin(BeetsPlugin):

    def __init__(self):
        super(KeyFinderPlugin, self).__init__()
        self.config.add({
            u'bin': u'KeyFinder',
            u'auto': True,
            u'overwrite': False,
        })
        self.config['auto'].get(bool)
        self.import_stages = [self.imported]

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
                log.error(u'KeyFinder execution failed: {0}'.format(exc))
                continue

            item['initial_key'] = key
            log.debug(u'added computed initial key {0} for {1}'
                      .format(key, util.displayable_path(item.path)))
            item.try_write()
            item.store()
