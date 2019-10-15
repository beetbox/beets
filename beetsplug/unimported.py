# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
import os

from beets import util, config
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand


class Unimported(BeetsPlugin):

    def __init__(self):
        super(Unimported, self).__init__()
        self.config.add(
            {
                'ignore_extensions': []
            }
        )

    def commands(self):
        def print_unimported(lib, opts, args):
            exts_to_ignore = self.config['ignore_extensions'].as_str_seq()
            in_folder = set(
                (os.path.join(r, file) for r, d, f in os.walk(lib.directory)
                 for file in f if not any(
                    [file.endswith(extension.encode()) for extension in
                     exts_to_ignore])))
            in_library = set(x.path for x in lib.items())
            art_files = set(x.artpath for x in lib.albums())
            for f in in_folder - in_library - art_files:
                print(util.displayable_path(f))

        unimported = Subcommand(
            'unimported',
            help='list all files in the library folder which are not listed'
                 ' in the beets library database')
        unimported.func = print_unimported
        return [unimported]
