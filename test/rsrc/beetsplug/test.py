from beets.plugins import BeetsPlugin
from beets import ui

class TestPlugin(BeetsPlugin):
    def __init__(self):
        super(TestPlugin, self).__init__()

    def commands(self):
        cmd = ui.Subcommand('test')
        cmd.func = lambda *args: None
        return [cmd]
