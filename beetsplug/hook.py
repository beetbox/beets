# -*- coding: utf-8 -*-
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

import string
import subprocess
import six

from beets.plugins import BeetsPlugin
from beets.util import shlex_split, arg_encoding


class CodingFormatter(string.Formatter):
    """A variant of `string.Formatter` that converts everything to `unicode`
    strings.

    This is necessary on Python 2, where formatting otherwise occurs on
    bytestrings. It intercepts two points in the formatting process to decode
    the format string and all fields using the specified encoding. If decoding
    fails, the values are used as-is.
    """

    def __init__(self, coding):
        """Creates a new coding formatter with the provided coding."""
        self._coding = coding

    def format(self, format_string, *args, **kwargs):
        """Formats the provided string using the provided arguments and keyword
        arguments.

        This method decodes the format string using the formatter's coding.

        See str.format and string.Formatter.format.
        """
        try:
            format_string = format_string.decode(self._coding)
        except UnicodeEncodeError:
            pass

        return super(CodingFormatter, self).format(format_string, *args,
                                                   **kwargs)

    def convert_field(self, value, conversion):
        """Converts the provided value given a conversion type.

        This method decodes the converted value using the formatter's coding.

        See string.Formatter.convert_field.
        """
        converted = super(CodingFormatter, self).convert_field(value,
                                                               conversion)

        try:
            converted = converted.decode(self._coding)
        except UnicodeEncodeError:
            pass

        return converted


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

            hook_event = hook['event'].as_str()
            hook_command = hook['command'].as_str()

            self.create_and_register_hook(hook_event, hook_command)

    def create_and_register_hook(self, event, command):
        def hook_function(**kwargs):
                if command is None or len(command) == 0:
                    self._log.error('invalid command "{0}"', command)
                    return

                # Use a string formatter that works on Unicode strings.
                if six.PY2:
                    formatter = CodingFormatter(arg_encoding())
                else:
                    formatter = string.Formatter()

                command_pieces = shlex_split(command)

                for i, piece in enumerate(command_pieces):
                    command_pieces[i] = formatter.format(piece, event=event,
                                                         **kwargs)

                self._log.debug(u'running command "{0}" for event {1}',
                                u' '.join(command_pieces), event)

                try:
                    subprocess.Popen(command_pieces).wait()
                except OSError as exc:
                    self._log.error(u'hook for {0} failed: {1}', event, exc)

        self.register_listener(event, hook_function)
