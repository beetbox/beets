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

"""Uses Librosa and matplotlib to output a spectrogram image."""

from __future__ import annotations

from typing import TYPE_CHECKING

import librosa
import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand

if TYPE_CHECKING:
    from beets.importer import ImportTask
    from beets.library import Item, Library


class SpectrogramPlugin(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.config.add(
            {
                "auto": True,
                "width": 800,
                "height": 300,
                "transparent": False
            }
        )

        if self.config["auto"]:
            self.import_stages = [self.imported]

    def commands(self) -> list[Subcommand]:
        cmd = Subcommand(
            "spectrogram", help="generate a spectrogram image file"
        )
        cmd.parser.add_option(
            "--width",
            dest="width",
            type="int",
            default=800,
            help="image width (e.g: 800)",
        )
        cmd.parser.add_option(
            "--height",
            dest="height",
            type="int",
            default=300,
            help="image height (e.g: 300)",
        )
        cmd.parser.add_option(
            "-t",
            "--transparent",
            dest="transparent",
            action="store_true",
            default=False,
            help="transparent background",
        )
        cmd.func = self.command
        return [cmd]

    def command(self, lib: Library, opts, args: list[str]) -> None:
        width = int(opts.width) or self.config["width"].get(int)
        height = int(opts.height) or self.config["height"].get(int)
        transparent = opts.transparent or self.config["transparent"].get(bool)
        self.generate_image(
            list(lib.items(args)),
            width,
            height,
            transparent
        )

    def imported(self, _, task: ImportTask) -> None:
        self.generate_image(
            task.imported_items(),
            width=self.config["width"].get(int),
            height=self.config["height"].get(int),
        )

    def generate_image(
        self,
        items: list[Item],
        width: int = 800,
        height: int = 300,
        transparent: bool = False
    ) -> None:
        for item in items:
            file_path = item.filepath
            image_path = file_path.with_name(f"{file_path.stem} (spectrogram {width}x{height})").with_suffix(".png")
            image_dpi = 100

            try:
                waveform, sample_rate = librosa.load(file_path)
                spectrogram = librosa.amplitude_to_db(np.abs(librosa.stft(waveform)), ref=np.max)

            except Exception as exc:
                self._log.error("Failed to load {}: {}", file_path, exc)
                continue

            try:
                plt.figure(figsize=(width / image_dpi, height / image_dpi))
                librosa.display.specshow(spectrogram, sr=sample_rate, x_axis="time", y_axis="log")
                plt.colorbar(format="%+2.f dB")
                plt.title("Spectrogram (dB)")
                plt.tight_layout()

                plt.savefig(image_path, dpi=image_dpi, transparent=transparent)

            except Exception as exc:
                self._log.error("Failed to write {}: {}", image_path, exc)
                continue

