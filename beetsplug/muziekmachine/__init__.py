from beets.plugins import BeetsPlugin
from .cli.import_command import custom_import_cmd

class Pipe(BeetsPlugin):
    def commands(self):
        return [custom_import_cmd]
