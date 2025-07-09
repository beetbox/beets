# This file is part of beets.
# Copyright 2019, Joris Jensen
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

"""
List all files in the library folder which are not listed in the
 beets library database, including art files
"""

import os

from beets import util
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, print_

__author__ = "https://github.com/MrNuggelz"


class Unimported(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.config.add(
            {
                "ignore_extensions": [],
                "ignore_subdirectories": [],
                "ignore_as_globs": False,
            }
        )

    def walk(self, lib):
        ignore_subdirs = self.config["ignore_subdirectories"].as_str_seq()
        if self.config["ignore_as_globs"].get(bool):
            # The way beets ignore elements in the library, using globbing,
            #   whatever the depth
            for root, _, files in util.sorted_walk(
                lib.directory, ignore=ignore_subdirs
            ):
                yield (root, files)
        else:
            # the reverse-compatible search, with ignore_subdirectories as
            #   a direct child of the library root
            ignore_dirs = [
                os.path.join(lib.directory, x.encode()) for x in ignore_subdirs
            ]
            for root, _, files in os.walk(lib.directory):
                # do not traverse if root is a child of an ignored directory
                if any(root.startswith(ignored) for ignored in ignore_dirs):
                    continue
                yield (root, files)

    def commands(self):
        def print_unimported(lib, opts, args):
            ignore_exts = [
                ("." + x).encode()
                for x in self.config["ignore_extensions"].as_str_seq()
            ]
            in_folder = set()
            for root, files in self.walk(lib):
                for file in files:
                    # ignore files with ignored extensions
                    if any(file.endswith(ext) for ext in ignore_exts):
                        continue
                    in_folder.add(os.path.join(root, file))

            in_library = {x.path for x in lib.items()}
            art_files = {x.artpath for x in lib.albums()}
            for f in in_folder - in_library - art_files:
                print_(util.displayable_path(f))

        unimported = Subcommand(
            "unimported",
            help="list all files in the library folder which are not listed"
            " in the beets library database",
        )
        unimported.func = print_unimported
        return [unimported]
