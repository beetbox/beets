"""Uses Librosa to calculate the `bpm` field."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import confuse
import librosa
import numpy as np
import scipy.stats

from beets import ui
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, should_write
from beets.util.deprecation import deprecate_for_user

if TYPE_CHECKING:
    from collections.abc import Iterable

    from beets.importer import ImportTask
    from beets.library import Item, Library

# Bounds used when only one of min_bpm/max_bpm is given. Same as the
# range librosa documents for uniform tempo priors.
DEFAULT_MIN_BPM = 40
DEFAULT_MAX_BPM = 280


class AutoBPMCLIOpts(Protocol):
    force: bool
    limit: int | None
    quiet: bool
    start_bpm: int | None
    min_bpm: int | None
    max_bpm: int | None


class AutoBPMPlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.config.add(
            {
                "auto": True,
                "force": False,
                "quiet": False,
                "min_bpm": None,
                "max_bpm": None,
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
        cmd.parser.add_option(
            "-b",
            "--start-bpm",
            dest="start_bpm",
            type="int",
            default=None,
            help="Initial BPM guess for beat tracking "
            "(overrides beat_track_kwargs.start_bpm)",
        )
        cmd.parser.add_option(
            "-m",
            "--min-bpm",
            dest="min_bpm",
            type="int",
            default=None,
            help="Lowest BPM to consider (overrides min_bpm)",
        )
        cmd.parser.add_option(
            "-M",
            "--max-bpm",
            dest="max_bpm",
            type="int",
            default=None,
            help="Highest BPM to consider (overrides max_bpm)",
        )
        cmd.parser.add_limit_option()
        cmd.func = self.command
        return [cmd]

    def beat_track_kwargs(
        self,
        start_bpm: int | None = None,
        min_bpm: int | None = None,
        max_bpm: int | None = None,
    ) -> dict[str, Any]:
        """Combine the configured beat_track kwargs with CLI overrides.

        A min/max range becomes a uniform tempo prior, which librosa uses
        instead of the start_bpm based one.
        """
        kwargs = dict(self.config["beat_track_kwargs"].flatten())
        if start_bpm is not None:
            kwargs["start_bpm"] = start_bpm

        if min_bpm is None:
            min_bpm = self.config["min_bpm"].get(confuse.Optional(int))
        if max_bpm is None:
            max_bpm = self.config["max_bpm"].get(confuse.Optional(int))

        self._log.debug("beat_track kwargs: {}", kwargs)
        if min_bpm is not None or max_bpm is not None:
            low = DEFAULT_MIN_BPM if min_bpm is None else min_bpm
            high = DEFAULT_MAX_BPM if max_bpm is None else max_bpm
            if low >= high:
                raise ui.UserError(
                    f"autobpm: min_bpm ({low}) must be lower than "
                    f"max_bpm ({high})"
                )
            self._log.debug("restricting BPM to {}-{}", low, high)
            kwargs["prior"] = scipy.stats.uniform(loc=low, scale=high - low)
        return kwargs

    def command(
        self, lib: Library, opts: AutoBPMCLIOpts, args: list[str]
    ) -> None:
        force = self.config["force"].get(bool) or opts.force
        quiet = self.config["quiet"].get(bool) or opts.quiet
        self.calculate_bpm(
            list(lib.items(args, limit=opts.limit)),
            write=should_write(),
            force=force,
            quiet=quiet,
            beat_track_kwargs=self.beat_track_kwargs(
                opts.start_bpm, opts.min_bpm, opts.max_bpm
            ),
        )

    def imported(self, _, task: ImportTask) -> None:
        self.calculate_bpm(
            task.imported_items(),
            force=self.config["force"].get(bool),
            quiet=self.config["quiet"].get(bool),
            beat_track_kwargs=self.beat_track_kwargs(),
        )

    def calculate_bpm(
        self,
        items: Iterable[Item],
        write: bool = False,
        force: bool = False,
        quiet: bool = False,
        beat_track_kwargs: dict[str, Any] | None = None,
    ) -> None:
        kwargs = beat_track_kwargs or {}
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
