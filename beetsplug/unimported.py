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

from beets import ui, util
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, print_

__author__ = "https://github.com/MrNuggelz"


class Unimported(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.config.add({"ignore_extensions": [], "ignore_subdirectories": []})

    def commands(self):
        def print_unimported(lib, opts, args):
            ignore_exts = [
                f".{x}".encode()
                for x in self.config["ignore_extensions"].as_str_seq()
            ]
            ignore_dirs = [
                os.path.join(lib.directory, x.encode())
                for x in self.config["ignore_subdirectories"].as_str_seq()
            ]

            in_library = {x.path for x in lib.items()}
            art_files = {x.artpath for x in lib.albums()}
            unimported_files = set()

            def dir_filter(root):
                # do not traverse if root is a child of an ignored directory
                return not any(
                    root.startswith(ignored) for ignored in ignore_dirs
                )

            def file_filter(file):
                # ignore files with ignored extensions or that are art files
                return (
                    not any(file.endswith(ext) for ext in ignore_exts)
                    and file not in art_files
                )

            with ui.changes_and_errors_pbars(
                desc="Scanning files",
                unit="files",
            ) as (_, n_unchanged, _):
                for root, _, files in os.walk(lib.directory):
                    if dir_filter(root):
                        for file in files:
                            if file_filter(file):
                                path = os.path.join(root, file)
                                if path not in in_library:
                                    unimported_files.add(path)
                                n_unchanged.update()

            for f in unimported_files:
                print_(util.displayable_path(f))

        unimported = Subcommand(
            "unimported",
            help="list all files in the library folder which are not listed"
            " in the beets library database",
        )
        unimported.func = print_unimported
        return [unimported]
