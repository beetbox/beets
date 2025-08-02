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

from __future__ import annotations

import os
import shlex
import string
import subprocess
from typing import Any

from beets.plugins import BeetsPlugin


class BytesToStrFormatter(string.Formatter):
    """A variant of `string.Formatter` that converts `bytes` to `str`."""

    def convert_field(self, value: Any, conversion: str | None) -> Any:
        """Converts the provided value given a conversion type.

        This method decodes the converted value using the formatter's coding.
        """
        converted = super().convert_field(value, conversion)

        if isinstance(converted, bytes):
            return os.fsdecode(converted)

        return converted


class HookPlugin(BeetsPlugin):
    """Allows custom commands to be run when an event is emitted by beets"""

    def __init__(self):
        super().__init__()

        self.config.add({"hooks": []})

        hooks = self.config["hooks"].get(list)

        for hook_index in range(len(hooks)):
            hook = self.config["hooks"][hook_index]

            hook_event = hook["event"].as_str()
            hook_command = hook["command"].as_str()

            self.create_and_register_hook(hook_event, hook_command)

    def create_and_register_hook(self, event, command):
        def hook_function(**kwargs):
            if command is None or len(command) == 0:
                self._log.error('invalid command "{}"', command)
                return

            # For backwards compatibility, use a string formatter that decodes
            # bytes (in particular, paths) to strings.
            formatter = BytesToStrFormatter()
            command_pieces = [
                formatter.format(piece, event=event, **kwargs)
                for piece in shlex.split(command)
            ]

            self._log.debug(
                'running command "{}" for event {}',
                " ".join(command_pieces),
                event,
            )

            try:
                subprocess.check_call(command_pieces)
            except subprocess.CalledProcessError as exc:
                self._log.error(
                    "hook for {} exited with status {}", event, exc.returncode
                )
            except OSError as exc:
                self._log.error("hook for {} failed: {}", event, exc)

        self.register_listener(event, hook_function)
