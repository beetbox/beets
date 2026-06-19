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

"""Uses Librosa and matplotlib to output a waveform image."""

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


class WaveformPlugin(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.config.add(
            {
                "auto": True,
                "width": 800,
                "height": 300,
                "transparent": False,
                "color": "black"
            }
        )

        if self.config["auto"]:
            self.import_stages = [self.imported]

    def commands(self) -> list[Subcommand]:
        cmd = Subcommand(
            "waveform", help="generate a waveform image file"
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
        cmd.parser.add_option(
            "-c",
            "--color",
            dest="color",
            default="black",
            help="waveform color (e.g: orange)",
        )
        cmd.func = self.command
        return [cmd]

    def command(self, lib: Library, opts, args: list[str]) -> None:
        width = int(opts.width) or self.config["width"].get(int)
        height = int(opts.height) or self.config["height"].get(int)
        transparent = opts.transparent or self.config["transparent"].get(bool)
        color = opts.color or self.config["color"].get(str)
        self.generate_image(
            list(lib.items(args)),
            width,
            height,
            transparent,
            color
        )

    def imported(self, _, task: ImportTask) -> None:
        self.generate_image(
            task.imported_items(),
            width=self.config["width"].get(int),
            height=self.config["height"].get(int),
            transparent=self.config["transparent"].get(bool),
            color=self.config["color"].get(str)
        )

    def generate_image(
        self,
        items: list[Item],
        width: int = 800,
        height: int = 300,
        transparent: bool = False,
        color: str = "black"
    ) -> None:
        for item in items:
            file_path = item.filepath
            image_path = file_path.with_name(f"{file_path.stem} (waveform {width}x{height})").with_suffix(".png")
            image_dpi = 100

            try:
                waveform, sample_rate = librosa.load(file_path)

            except Exception as exc:
                self._log.error("Failed to load {}: {}", file_path, exc)
                continue

            try:
                plt.figure(figsize=(width / image_dpi, height / image_dpi))
                librosa.display.waveshow(waveform, sr=sample_rate, color=color)

                plt.tight_layout()
                plt.axis("off")
                plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
                plt.margins(0, 0)

                plt.savefig(image_path, dpi=image_dpi, transparent=transparent)

            except Exception as exc:
                self._log.error("Failed to write {}: {}", image_path, exc)
                continue

