"""
List all files in the library folder which are not listed in the
 beets library database, including art files
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, print_

if TYPE_CHECKING:
    import optparse

    from beets.library import Library


__author__ = "https://github.com/MrNuggelz"


class Unimported(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.config.add({"ignore_extensions": [], "ignore_subdirectories": []})

    def commands(self) -> list[Subcommand]:
        def print_unimported(
            lib: Library, opts: optparse.Values, args: list[str]
        ) -> None:
            ignore_exts = {
                f".{x}" for x in self.config["ignore_extensions"].as_str_seq()
            }
            ignore_dirs = {
                lib.directory / x
                for x in self.config["ignore_subdirectories"].as_str_seq()
            }

            ignored: set[Path | None] = set()
            ignored.update(x.filepath for x in lib.items())
            ignored.update(x.art_filepath for x in lib.albums())
            for root, _, files in os.walk(lib.directory):
                root_path = Path(root)
                # do not traverse if root is a child of an ignored directory
                if set(root_path.parents) & ignore_dirs:
                    continue
                for file in map(Path, files):
                    # ignore files with ignored extensions
                    if file.suffix in ignore_exts:
                        continue
                    if (_path := (root_path / file)) not in ignored:
                        print_(str(_path))

        unimported = Subcommand(
            "unimported",
            help="list all files in the library folder which are not listed"
            " in the beets library database",
        )
        unimported.func = print_unimported
        return [unimported]
