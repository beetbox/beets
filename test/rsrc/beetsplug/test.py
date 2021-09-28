from beets.plugins import BeetsPlugin
from beets import ui


class TestPlugin(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.is_test_plugin = True

    def commands(self):
        test = ui.Subcommand('test')
        test.func = lambda *args: None

        # Used in CompletionTest
        test.parser.add_option('-o', '--option', dest='my_opt')

        plugin = ui.Subcommand('plugin')
        plugin.func = lambda *args: None
        return [test, plugin]
