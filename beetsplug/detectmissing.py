# This file is part of beets.
# Copyright 2025, Rebecca Turner.
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
"""Detect missing files and album art."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from beets import plugins, ui, util

if TYPE_CHECKING:
    import optparse

    from beets.library import Library


class DetectMissingPlugin(plugins.BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()

    def commands(self) -> list[ui.Subcommand]:
        cmd = ui.Subcommand(
            "detectmissing", help="Detect missing files and album art"
        )

        cmd.parser.add_option(
            "--delete",
            help="Also delete missing items from the library",
            action="store_true",
        )

        cmd.func = self.detect_missing

        return [cmd]

    def detect_missing(
        self, lib: Library, opts: optparse.Values, _args: list[str]
    ) -> None:
        should_delete: bool = opts.delete or False

        for album in lib.albums():
            art_filepath = album.art_filepath
            if art_filepath is not None and not art_filepath.exists():
                print(f"{art_filepath}")

                if should_delete:
                    with lib.transaction():
                        album.artpath = None
                        album.store(fields=["artpath"])

        for item in lib.items():
            if item.path is not None:
                path = Path(os.fsdecode(item.path))
                if not path.exists():
                    print(f"{path}")

                    if should_delete:
                        with lib.transaction():
                            item.remove(delete=False, with_album=True)
                        util.prune_dirs(
                            os.path.dirname(item.path), lib.directory
                        )
