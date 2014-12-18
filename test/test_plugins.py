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
import helper

from beets import plugins
from beets.library import Item
from beets.dbcore import types
from beets.mediafile import MediaFile


class TestHelper(helper.TestHelper):

    def setup_plugin_loader(self):
        # FIXME the mocking code is horrific, but this is the lowest and
        # earliest level of the plugin mechanism we can hook into.
        self._plugin_loader_patch = patch('beets.plugins.load_plugins')
        self._plugin_classes = set()
        load_plugins = self._plugin_loader_patch.start()

        def myload(names=()):
            plugins._classes.update(self._plugin_classes)
        load_plugins.side_effect = myload
        self.setup_beets()

    def teardown_plugin_loader(self):
        self._plugin_loader_patch.stop()
        self.unload_plugins()

    def register_plugin(self, plugin_class):
        self._plugin_classes.add(plugin_class)


class ItemTypesTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_plugin_loader()
        self.setup_beets()

    def tearDown(self):
        self.teardown_plugin_loader()
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


class ItemWriteTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_plugin_loader()
        self.setup_beets()

        class EventListenerPlugin(plugins.BeetsPlugin):
            pass
        self.event_listener_plugin = EventListenerPlugin
        self.register_plugin(EventListenerPlugin)

    def tearDown(self):
        self.teardown_plugin_loader()
        self.teardown_beets()

    def test_change_tags(self):

        def on_write(item=None, path=None, tags=None):
            if tags['artist'] == 'XXX':
                tags['artist'] = 'YYY'

        self.register_listener('write', on_write)

        item = self.add_item_fixture(artist='XXX')
        item.write()

        mediafile = MediaFile(item.path)
        self.assertEqual(mediafile.artist, 'YYY')

    def register_listener(self, event, func):
        self.event_listener_plugin.register_listener(event, func)


class ItemTypeConflictTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_plugin_loader()
        self.setup_beets()

    def tearDown(self):
        self.teardown_plugin_loader()
        self.teardown_beets()

    def test_mismatch(self):
        class EventListenerPlugin(plugins.BeetsPlugin):
            item_types = {'duplicate': types.INTEGER}

        class AdventListenerPlugin(plugins.BeetsPlugin):
            item_types = {'duplicate': types.FLOAT}

        self.event_listener_plugin = EventListenerPlugin
        self.advent_listener_plugin = AdventListenerPlugin
        self.register_plugin(EventListenerPlugin)
        self.register_plugin(AdventListenerPlugin)
        self.assertRaises(plugins.PluginConflictException,
                          plugins.types, Item
                          )

    def test_match(self):
        class EventListenerPlugin(plugins.BeetsPlugin):
            item_types = {'duplicate': types.INTEGER}

        class AdventListenerPlugin(plugins.BeetsPlugin):
            item_types = {'duplicate': types.INTEGER}

        self.event_listener_plugin = EventListenerPlugin
        self.advent_listener_plugin = AdventListenerPlugin
        self.register_plugin(EventListenerPlugin)
        self.register_plugin(AdventListenerPlugin)
        self.assertNotEqual(None, plugins.types(Item))


class HelpersTest(unittest.TestCase):

    def test_sanitize_choices(self):
        self.assertEqual(plugins.sanitize_choices(['A', 'Z'], ('A', 'B')),
                         ['A'])
        self.assertEqual(plugins.sanitize_choices(['A', 'A'], ('A')), ['A'])
        self.assertEqual(plugins.sanitize_choices(['D', '*', 'A'],
                         ('A', 'B', 'C', 'D')), ['D', 'B', 'C', 'A'])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
