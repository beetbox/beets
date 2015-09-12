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
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import subprocess
import sys

from beets.plugins import BeetsPlugin


def create_hook_function(log, event, command, shell, substitute_args):

    # TODO: Find a better way of piping STDOUT/STDERR/STDIN between the process
    #       and the user.
    #
    #       The issue with our current method is that we can only pesudo-pipe
    #       one (two if we count STDERR being piped to STDOUT) stream at a
    #       time, meaning we can't have both output and input simultaneously.
    #       This is due to how Popen.std(out/err) works, as
    #       Popen.std(out/err).readline() waits until a newline has been output
    #       to the stream before returning.

    # TODO: Find a better way of converting arguments to strings, as I
    #       currently have a feeling that forcing everything to utf-8 might
    #       end up causing a mess.

    def hook_function(**kwargs):
        hook_command = command

        for key in substitute_args:
            if key in kwargs:
                hook_command = hook_command.replace(substitute_args[key],
                                                    unicode(kwargs[key],
                                                            "utf-8"))

        log.debug('Running command {0} for event {1}', hook_command, event)

        subprocess.Popen(hook_command, shell=shell).wait()

    return hook_function


class HookPlugin(BeetsPlugin):
    """Allows custom commands to be run when an event is emitted by beets"""
    def __init__(self):
        super(HookPlugin, self).__init__()

        self.config.add({
            'hooks': [],
            'substitute_event': '%EVENT%',
            'shell': True
        })

        hooks = self.config['hooks'].get(list)
        global_substitute_event = self.config['substitute_event'].get()
        global_shell = self.config['shell'].get(bool)

        for hook_index in range(len(hooks)):
            hook = self.config['hooks'][hook_index]

            hook_event = hook['event'].get()
            hook_command = hook['command'].get()

            if 'substitute_event' in hook:
                original = hook['substitute_event'].get()
            else:
                original = global_substitute_event

            if 'shell' in hook:
                shell = hook['shell'].get(bool)
            else:
                shell = global_shell

            if 'substitute_args' in hook:
                substitute_args = hook['substitute_args'].get(dict)
            else:
                substitute_args = {}

            hook_command = hook_command.replace(original, hook_event)
            hook_function = create_hook_function(self._log, hook_event,
                                                 hook_command, shell,
                                                 substitute_args)

            self.register_listener(hook_event, hook_function)
