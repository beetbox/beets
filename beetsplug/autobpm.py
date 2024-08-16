# This file is part of beets.
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

"""Uses Librosa to calculate the `bpm` field."""

from __future__ import annotations

from typing import Iterable

import librosa

from beets import util
from beets.importer import ImportTask
from beets.library import Item, Library
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, should_write


class AutoBPMPlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.config.add(
            {
                "auto": True,
                "overwrite": False,
                "beat_track_kwargs": {},
            }
        )

        if self.config["auto"]:
            self.import_stages = [self.imported]

    def commands(self) -> list[Subcommand]:
        cmd = Subcommand(
            "autobpm", help="detect and add bpm from audio using Librosa"
        )
        cmd.func = self.command
        return [cmd]

    def command(self, lib: Library, _, args: list[str]) -> None:
        self.calculate_bpm(list(lib.items(args)), write=should_write())

    def imported(self, _, task: ImportTask) -> None:
        self.calculate_bpm(task.imported_items())

    def calculate_bpm(self, items: list[Item], write: bool = False) -> None:
        for item in items:
            if item["bpm"]:
                self._log.info(
                    "found bpm {0} for {1}",
                    item["bpm"],
                    util.displayable_path(item.path),
                )
                if not self.config["overwrite"]:
                    continue

            try:
                y, sr = librosa.load(
                    util.syspath(item.path), res_type="kaiser_fast"
                )
            except Exception as exc:
                self._log.error(
                    "Failed to load {0}: {1}",
                    util.displayable_path(item.path),
                    exc,
                )
                continue

            kwargs = self.config["beat_track_kwargs"].flatten()
            try:
                tempo, _ = librosa.beat.beat_track(y=y, sr=sr, **kwargs)
            except Exception as exc:
                self._log.error(
                    "Failed to measure BPM for {0}: {1}",
                    util.displayable_path(item.path),
                    exc,
                )
                continue

            bpm = round(tempo[0] if isinstance(tempo, Iterable) else tempo)
            item["bpm"] = bpm
            self._log.info(
                "added computed bpm {0} for {1}",
                bpm,
                util.displayable_path(item.path),
            )

            if write:
                item.try_write()
            item.store()
