# This file is part of beets.
# Copyright 2014, Thomas Scholtes.
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

from mock import patch
from _common import unittest
from helper import TestHelper

from beets import plugins
from beets.library import Item
from beets.dbcore import types


class PluginTest(unittest.TestCase, TestHelper):

    def setUp(self):
        # FIXME the mocking code is horrific, but this is the lowest and
        # earliest level of the plugin mechanism we can hook into.
        self._plugin_loader_patch = patch('beets.plugins.load_plugins')
        self._plugin_classes = set()
        load_plugins = self._plugin_loader_patch.start()

        def myload(names=()):
            plugins._classes.update(self._plugin_classes)
        load_plugins.side_effect = myload
        self.setup_beets()

    def tearDown(self):
        self._plugin_loader_patch.stop()
        self.unload_plugins()
        self.teardown_beets()

    def test_flex_field_type(self):
        class RatingPlugin(plugins.BeetsPlugin):
            item_types = {'rating': types.Float()}

        self.register_plugin(RatingPlugin)
        self.config['plugins'] = 'rating'

        item = Item(path='apath', artist='aaa')
        item.add(self.lib)

        # Do not match unset values
        out = self.run_with_output('ls', 'rating:1..3')
        self.assertNotIn('aaa', out)

        self.run_command('modify', 'rating=2', '--yes')

        # Match in range
        out = self.run_with_output('ls', 'rating:1..3')
        self.assertIn('aaa', out)

        # Don't match out of range
        out = self.run_with_output('ls', 'rating:3..5')
        self.assertNotIn('aaa', out)

    def register_plugin(self, plugin_class):
        self._plugin_classes.add(plugin_class)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
