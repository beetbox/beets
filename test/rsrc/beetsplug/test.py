# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets import ui


class TestPlugin(BeetsPlugin):
    def __init__(self):
        super(TestPlugin, self).__init__()
        self.is_test_plugin = True

    def commands(self):
        test = ui.Subcommand('test')
        test.func = lambda *args: None

        # Used in CompletionTest
        test.parser.add_option(u'-o', u'--option', dest='my_opt')

        plugin = ui.Subcommand('plugin')
        plugin.func = lambda *args: None
        return [test, plugin]
