# This file is part of beets.
# Copyright 2015, Adrian Sampson.
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

"""Allows custom commands to be run when an event is emitted by beets"""
from __future__ import division, absolute_import, print_function

import shlex
import subprocess

from beets.plugins import BeetsPlugin
from beets.ui import _arg_encoding


class HookPlugin(BeetsPlugin):
    """Allows custom commands to be run when an event is emitted by beets"""
    def __init__(self):
        super(HookPlugin, self).__init__()

        self.config.add({
            'hooks': []
        })

        hooks = self.config['hooks'].get(list)

        for hook_index in range(len(hooks)):
            hook = self.config['hooks'][hook_index]

            hook_event = hook['event'].get()
            hook_command = hook['command'].get()

            self.create_and_register_hook(hook_event, hook_command)

    def create_and_register_hook(self, event, command):
        def hook_function(**kwargs):
                if command is None or len(command) == 0:
                    self._log.error('invalid command "{0}"', command)
                    return

                formatted_command = command.format(event=event, **kwargs)
                encoded_command = formatted_command.decode(_arg_encoding())
                command_pieces = shlex.split(encoded_command)

                self._log.debug('Running command "{0}" for event {1}',
                                encoded_command, event)

                try:
                    subprocess.Popen(command_pieces).wait()
                except OSError as exc:
                    self._log.error('hook for {0} failed: {1}', event, exc)

        self.register_listener(event, hook_function)
