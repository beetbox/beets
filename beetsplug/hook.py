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
import shlex
import subprocess

from beets.plugins import BeetsPlugin
from beets.ui import _arg_encoding


# Sadly we need this class for {} support due to issue 13598
# https://bugs.python.org/issue13598
# https://bugs.python.org/file25816/issue13598.diff
class AutoFieldCountFormatter(string.Formatter):
    def _vformat(self, format_string, args, kwargs, used_args,
                 recursion_depth):
        if recursion_depth < 0:
            raise ValueError('Max string recursion exceeded')
        auto_field_count = 0
        # manual numbering
        manual = None
        result = []
        for literal_text, field_name, format_spec, conversion in \
                self.parse(format_string):

            # output the literal text
            if literal_text:
                result.append(literal_text)

            # if there's a field, output it
            if field_name is not None:
                # this is some markup, find the object and do
                #  the formatting

                # ensure we are consistent with numbering
                if (field_name == "" and manual) or manual is False:
                    raise ValueError("cannot switch from manual field " +
                                     "specification to automatic field " +
                                     "numbering")

                # automatic numbering
                if field_name == "":
                    manual = False
                    field_name = str(auto_field_count)
                    auto_field_count += 1

                # manual numbering
                else:
                    manual = True

                # given the field_name, find the object it references
                #  and the argument it came from
                obj, arg_used = self.get_field(field_name, args, kwargs)
                used_args.add(arg_used)

                # do any conversion on the resulting object
                obj = self.convert_field(obj, conversion)

                # expand the format spec, if needed
                format_spec = self._vformat(format_spec, args, kwargs,
                                            used_args, recursion_depth - 1)

                # format the object and append to the result
                result.append(self.format_field(obj, format_spec))

        return ''.join(result)


class CodingFormatter(AutoFieldCountFormatter):
    def __init__(self, coding):
        self._coding = coding

    def format(self, format_string, *args, **kwargs):
        try:
            format_string = format_string.decode(self._coding)
        except UnicodeEncodeError:
            pass

        return super(CodingFormatter, self).format(format_string, *args,
                                                   **kwargs)

    def convert_field(self, value, conversion):
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

            hook_event = hook['event'].get()
            hook_command = hook['command'].get()

            self.create_and_register_hook(hook_event, hook_command)

    def create_and_register_hook(self, event, command):
        def hook_function(**kwargs):
                if command is None or len(command) == 0:
                    self._log.error('invalid command "{0}"', command)
                    return

                encoding = _arg_encoding()
                formatter = CodingFormatter(encoding)
                formatted_command = formatter.format(command, event=event,
                                                     **kwargs)
                encoded_formatted_command = formatted_command.encode(encoding)
                command_pieces = shlex.split(encoded_formatted_command)
                decoded_command_pieces = map(lambda piece:
                                             piece.decode(encoding),
                                             command_pieces)

                self._log.debug(u'running command "{0}" for event {1}',
                                formatted_command, event)

                try:
                    subprocess.Popen(decoded_command_pieces).wait()
                except OSError as exc:
                    self._log.error(u'hook for {0} failed: {1}', event, exc)

        self.register_listener(event, hook_function)
