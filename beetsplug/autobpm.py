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

from typing import TYPE_CHECKING

import librosa
import numpy as np

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, should_write
from beets.util.deprecation import deprecate_for_user

if TYPE_CHECKING:
    from beets.importer import ImportTask
    from beets.library import Item, Library


class AutoBPMPlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.config.add(
            {
                "auto": True,
                "force": False,
                "quiet": False,
                "beat_track_kwargs": {},
            }
        )

        if self.config["overwrite"].exists():
            deprecate_for_user(
                self._log,
                f"'{self.name}.overwrite' configuration option",
                f"'{self.name}.force'",
            )
            self.config["force"] = self.config["overwrite"].get()

        if self.config["auto"]:
            self.import_stages = [self.imported]

    def commands(self) -> list[Subcommand]:
        cmd = Subcommand(
            "autobpm", help="detect and add bpm from audio using Librosa"
        )
        cmd.parser.add_option(
            "-f",
            "--force",
            dest="force",
            action="store_true",
            default=False,
            help="Overwrite existing BPM values",
        )
        cmd.parser.add_option(
            "-q",
            "--quiet",
            dest="quiet",
            action="store_true",
            default=False,
            help="Suppress message when item already has BPM",
        )
        cmd.func = self.command
        return [cmd]

    def command(self, lib: Library, opts, args: list[str]) -> None:
        force = self.config["force"].get(bool) or opts.force
        quiet = self.config["quiet"].get(bool) or opts.quiet
        self.calculate_bpm(
            list(lib.items(args)),
            write=should_write(),
            force=force,
            quiet=quiet,
        )

    def imported(self, _, task: ImportTask) -> None:
        self.calculate_bpm(
            task.imported_items(),
            force=self.config["force"].get(bool),
            quiet=self.config["quiet"].get(bool),
        )

    def calculate_bpm(
        self,
        items: list[Item],
        write: bool = False,
        force: bool = False,
        quiet: bool = False,
    ) -> None:
        for item in items:
            path = item.filepath
            if bpm := item.bpm:
                if not quiet:
                    self._log.info("BPM for {} already exists: {}", path, bpm)
                if not force:
                    continue
            try:
                y, sr = librosa.load(item.filepath, res_type="kaiser_fast")
            except Exception as exc:
                self._log.error("Failed to load {}: {}", path, exc)
                continue

            kwargs = self.config["beat_track_kwargs"].flatten()
            try:
                tempo, _ = librosa.beat.beat_track(y=y, sr=sr, **kwargs)
            except Exception as exc:
                self._log.error("Failed to measure BPM for {}: {}", path, exc)
                continue

            bpm = round(
                float(tempo[0] if isinstance(tempo, np.ndarray) else tempo)
            )

            item["bpm"] = bpm
            self._log.info("Computed BPM for {}: {}", path, bpm)

            if write:
                item.try_write()
            item.store()
