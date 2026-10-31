"""Uses Librosa to calculate the `bpm` field."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import librosa
import numpy as np

from beets import util
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, should_write
from beets.util.deprecation import deprecate_for_user

if TYPE_CHECKING:
    from collections.abc import Iterable

    from beets.importer import ImportTask
    from beets.library import Item, Library


class AutoBPMCLIOpts(Protocol):
    limit: int | None


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
            default=None,
            help="Overwrite existing BPM values",
        )
        cmd.parser.add_option(
            "-q",
            "--quiet",
            dest="quiet",
            action="store_true",
            default=None,
            help="Suppress message when item already has BPM",
        )
        cmd.parser.add_option(
            "-b",
            "--start-bpm",
            dest="beat_track_kwargs.start_bpm",
            type="int",
            action="callback",
            callback=util.positive_int_option_callback,
            help=(
                "Initial BPM guess for beat tracking "
                "(overrides beat_track_kwargs.start_bpm)"
            ),
        )
        cmd.parser.add_limit_option()
        cmd.func = self.command
        return [cmd]

    def command(
        self, lib: Library, opts: AutoBPMCLIOpts, args: list[str]
    ) -> None:
        self.config.set_args(vars(opts), dots=True)
        self.calculate_bpm(
            list(lib.items(args, limit=opts.limit)), write=should_write()
        )

    def imported(self, _, task: ImportTask) -> None:
        self.calculate_bpm(task.imported_items())

    def calculate_bpm(self, items: Iterable[Item], write: bool = False) -> None:
        force = self.config["force"].get(bool)
        quiet = self.config["quiet"].get(bool)
        kwargs = self.config["beat_track_kwargs"].flatten()
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

            self._log.debug("beat_track kwargs for {}: {}", path, kwargs)
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
