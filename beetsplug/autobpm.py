"""Uses Librosa to calculate the `bpm` field."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypedDict, cast

import confuse
import librosa
import numpy as np
import scipy.stats

from beets import ui, util
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, should_write
from beets.util.deprecation import deprecate_for_user

if TYPE_CHECKING:
    from collections.abc import Iterable

    from beets.importer import ImportTask
    from beets.library import Item, Library

# Bounds used when only one of min_bpm/max_bpm is given.
DEFAULT_MIN_BPM = 40
DEFAULT_MAX_BPM = 320

# The tempos librosa can pick from depend on the sample rate, the hop length
# and the autocorrelation window. These mirror librosa defaults, see
# https://librosa.org/doc/latest/api/generated/librosa.load.html (sr) and
# https://librosa.org/doc/latest/api/generated/librosa.feature.tempo.html
# (hop_length, ac_size, max_tempo). beat_track exposes only the hop length.
# Audio is loaded at SAMPLE_RATE explicitly.
SAMPLE_RATE = 22050
DEFAULT_HOP_LENGTH = 512
AUTOCORRELATION_SECONDS = 8.0
# librosa ignores tempo candidates at or above this value.
LIBROSA_MAX_TEMPO = 320


def has_tempo_candidates(low: int, high: int, hop_length: int) -> bool:
    """Whether librosa has a tempo bin inside the closed range [low, high].

    librosa only scores discrete tempos derived from autocorrelation lags, so
    a narrow range can contain none. All scores would then be -inf and the
    estimate would be infinite.
    """
    window = librosa.time_to_frames(
        AUTOCORRELATION_SECONDS, sr=SAMPLE_RATE, hop_length=hop_length
    ).item()
    tempos = librosa.tempo_frequencies(
        window, sr=SAMPLE_RATE, hop_length=hop_length
    )
    usable = (tempos >= low) & (tempos <= high) & (tempos < LIBROSA_MAX_TEMPO)
    return bool(usable.any())


class AutoBPMCLIOpts(Protocol):
    force: bool | None
    limit: int | None
    quiet: bool | None
    # --start-bpm is not listed: its dotted dest ("beat_track_kwargs.start_bpm")
    # is not a valid attribute name and is only read via config.set_args().
    min_bpm: int | None
    max_bpm: int | None


class BeatTrackKwargs(TypedDict, total=False):
    """Keyword arguments forwarded to `librosa.beat.beat_track`."""

    start_bpm: float
    hop_length: int
    tightness: float
    trim: bool
    bpm: float
    prior: scipy.stats.rv_continuous


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
            callback=util.parse_positive_int,
            help=(
                "Initial BPM guess for beat tracking "
                "(overrides beat_track_kwargs.start_bpm)"
            ),
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
    ) -> BeatTrackKwargs:
        """Combine the configured beat_track kwargs with CLI overrides.

        A min/max range becomes a uniform tempo prior, which librosa uses
        instead of the start_bpm based one.
        """
        kwargs = cast(
            BeatTrackKwargs, self.config["beat_track_kwargs"].flatten()
        )
        if start_bpm is not None:
            kwargs["start_bpm"] = start_bpm

        if min_bpm is None:
            min_bpm = self.config["min_bpm"].get(confuse.Optional(int))
        if max_bpm is None:
            max_bpm = self.config["max_bpm"].get(confuse.Optional(int))

        self._log.debug("beat_track kwargs: {}", dict(kwargs))
        if min_bpm is not None or max_bpm is not None:
            low = DEFAULT_MIN_BPM if min_bpm is None else min_bpm
            high = DEFAULT_MAX_BPM if max_bpm is None else max_bpm
            if low >= high:
                raise ui.UserError(
                    f"autobpm: min_bpm ({low}) must be lower than "
                    f"max_bpm ({high})"
                )
            hop_length = kwargs.get("hop_length", DEFAULT_HOP_LENGTH)
            if not has_tempo_candidates(low, high, hop_length):
                raise ui.UserError(
                    f"autobpm: no tempo can be detected between min_bpm "
                    f"({low}) and max_bpm ({high}), widen the range"
                )
            self._log.debug("restricting BPM to {}-{}", low, high)
            kwargs["prior"] = scipy.stats.uniform(loc=low, scale=high - low)
        return kwargs

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
        kwargs = self.beat_track_kwargs(
            start_bpm=self.config["start_bpm"].get(confuse.Optional(int)),
            min_bpm=self.config["min_bpm"].get(confuse.Optional(int)),
            max_bpm=self.config["max_bpm"].get(confuse.Optional(int)),
        )

        for item in items:
            path = item.filepath
            if bpm := item.bpm:
                if not quiet:
                    self._log.info("BPM for {} already exists: {}", path, bpm)
                if not force:
                    continue
            try:
                y, sr = librosa.load(
                    item.filepath, sr=SAMPLE_RATE, res_type="kaiser_fast"
                )
            except Exception as exc:
                self._log.error("Failed to load {}: {}", path, exc)
                continue

            self._log.debug("beat_track kwargs for {}: {}", path, kwargs)
            try:
                tempo, _ = librosa.beat.beat_track(y=y, sr=sr, **kwargs)
            except Exception as exc:
                self._log.error("Failed to measure BPM for {}: {}", path, exc)
                continue

            tempo = float(tempo[0] if isinstance(tempo, np.ndarray) else tempo)
            if not np.isfinite(tempo):
                self._log.error(
                    "Failed to measure BPM for {}: got {}", path, tempo
                )
                continue

            bpm = round(tempo)

            item["bpm"] = bpm
            self._log.info("Computed BPM for {}: {}", path, bpm)

            if write:
                item.try_write()
            item.store()
