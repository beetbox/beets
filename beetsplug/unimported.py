import os

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand


class Unimported(BeetsPlugin):

    def __init__(self):
        super(Unimported, self).__init__()
        self.config.add(
            {
                'ignore_extensions': '[]'
            }
        )

    def commands(self):
        def print_unimported(lib, opts, args):
            in_library = set((os.path.join(r, file) for r, d, f in os.walk(lib.directory) for file in f if
                              not any([file.endswith(extension.encode()) for extension in self.config['ignore_extensions'].get()])))
            test = set((x.path for x in lib.items()))
            for f in in_library - test:
                print(f.decode('utf-8'))

        unimported = Subcommand('unimported', help='list files in library which have not been imported')
        unimported.func = print_unimported
        return [unimported]
