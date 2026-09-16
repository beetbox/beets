"""Determine BPM by pressing a key to the rhythm."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from beets import ui
from beets.plugins import BeetsPlugin

if TYPE_CHECKING:
    import optparse
    from collections.abc import Sequence

    from beets.library import Item, Library


def bpm(max_strokes: int) -> float:
    """Returns average BPM (possibly of a playing song)
    listening to Enter keystrokes.
    """
    t0 = None
    dt = []
    for i in range(max_strokes):
        # Press enter to the rhythm...
        s = input()
        if s == "":
            t1 = time.time()
            # Only start measuring at the second stroke
            if t0:
                dt.append(t1 - t0)
            t0 = t1
        else:
            break

    # Return average BPM
    # bpm = (max_strokes-1) / sum(dt) * 60
    return sum([1.0 / dti * 60 for dti in dt]) / len(dt)


class BPMPlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.config.add({"max_strokes": 3, "overwrite": True})

    def commands(self) -> list[ui.Subcommand]:
        cmd = ui.Subcommand(
            "bpm",
            help="determine bpm of a song by pressing a key to the rhythm",
        )
        cmd.func = self.command
        return [cmd]

    def command(
        self, lib: Library, opts: optparse.Values, args: list[str]
    ) -> None:
        write = ui.should_write()
        self.get_bpm(lib.items(args), write)

    def get_bpm(self, items: Sequence[Item], write: bool = False) -> None:
        overwrite = self.config["overwrite"].get(bool)
        if len(items) > 1:
            raise ValueError("Can only get bpm of one song at time")

        item = items[0]
        if item["bpm"]:
            self._log.info("Found bpm {}", item["bpm"])
            if not overwrite:
                return

        self._log.info(
            "Press Enter {} times to the rhythm or Ctrl-D to exit",
            self.config["max_strokes"].get(int),
        )
        new_bpm = bpm(self.config["max_strokes"].get(int))
        item["bpm"] = int(new_bpm)
        if write:
            item.try_write()
        item.store()
        self._log.info("Added new bpm {}", item["bpm"])
