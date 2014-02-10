from beets.plugins import BeetsPlugin
from beets import ui

class TestPlugin(BeetsPlugin):
    def __init__(self):
        super(TestPlugin, self).__init__()
        self.is_test_plugin = True

    def commands(self):
        test = ui.Subcommand('test')
        test.func = lambda *args: None
        plugin = ui.Subcommand('plugin')
        plugin.func = lambda *args: None
        return [test, plugin]
