from beets.plugins import BeetsPlugin
from beets.ui import Subcommand

def replace(lib, opts, args):
    print("Hello!")

class ReplacePlugin(BeetsPlugin):
    def commands(self):
        return [replace_command]

replace_command = Subcommand('replace', help='This command replaces the target audio file, while keeping tags intact')
replace_command.func = replace
