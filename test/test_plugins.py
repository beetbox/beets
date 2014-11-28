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
import os

from mock import patch
import shutil
from _common import unittest
import helper

from beets import plugins, config
from beets.library import Item
from beets.dbcore import types
from beets.mediafile import MediaFile
from test import _common
from test.test_importer import ImportHelper, AutotagStub


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

class FileFilterPluginTest(_common.TestCase, ImportHelper):
    """ Test the file filter plugin interface
    """
    def setUp(self):
        super(FileFilterPluginTest, self).setUp()
        self.setup_beets()
        self._create_import_dir(1)
        self._setup_import_session()
        config['import']['enumerate_only'] = True
        self.matcher = AutotagStub().install()
#        self.io.install()

        plugins.file_filters = self.file_filters

        self.filters = []

    def file_filters(self):
        return self.filters

    def filter_nothing(self, path, base):
        return False

    def filter_all(self, path, base):
        return True

    def filter_two(self, path, base):
        return '2' in base

    def tearDown(self):
        self.teardown_beets()
        self.matcher.restore()

    def test_import(self):
        resource_path = os.path.join(_common.RSRC, u'empty.mp3')
        single_path = os.path.join(self.import_dir, u'track_2.mp3')

        shutil.copy(resource_path, single_path)
        import_files = [
            os.path.join(self.import_dir, u'the_album'),
            single_path
        ]
        self._setup_import_session(singletons=True)
        self.importer.paths = import_files

        # Filter will return False every time
        self.filters = [self.filter_nothing]
        lines = self.run_import()
        self.assertEqual(len(lines), 0)

        # Filter will return True every time
        self.filters = [self.filter_all]
        lines = self.run_import()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], os.path.join(import_files[0], u'track_1.mp3'))
        self.assertEqual(lines[1], import_files[1])

        # Filter will return True if the file contains '2'
        self.filters = [self.filter_two]
        lines = self.run_import()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], import_files[1])

    def run_import(self):
        self.io.restore()
        self.io.install()
        self.importer.run()
        out = self.io.getoutput()

        return out.splitlines()

class FileFilterPluginTest(_common.TestCase, ImportHelper):
    """ Test the file filter plugin interface
    """
    def setUp(self):
        super(FileFilterPluginTest, self).setUp()
        self.setup_beets()
        self._create_import_dir(1)
        self._setup_import_session()
        config['import']['enumerate_only'] = True
        self.matcher = AutotagStub().install()

        self.old_file_filters = plugins.file_filters
        plugins.file_filters = self.file_filters

        self.filters = []

    def file_filters(self):
        return self.filters

    def filter_nothing(self, path, base):
        return False

    def filter_all(self, path, base):
        return True

    def filter_two(self, path, base):
        return '2' in base

    def tearDown(self):
        self.teardown_beets()
        self.matcher.restore()
        plugins.file_filters = self.old_file_filters

    def test_import_album(self):
        self._setup_import_session(singletons=False)
        self.__run_import_tests()

    def test_import_singleton(self):
        self._setup_import_session(singletons=True)
        self.__run_import_tests()

    def __run_import_tests(self):
        resource_path = os.path.join(_common.RSRC, u'empty.mp3')
        single_path = os.path.join(self.import_dir, u'track_2.mp3')

        shutil.copy(resource_path, single_path)
        import_files = [
            os.path.join(self.import_dir, u'the_album'),
            single_path
        ]
        self.importer.paths = import_files

        # Filter will return False every time
        self.filters = [self.filter_nothing]
        self.__run([])

        # Filter will return True every time
        self.filters = [self.filter_all]
        self.__run([os.path.join(import_files[0], u'track_1.mp3'),
                    import_files[1]])

        # Filter will return True if the file contains '2'
        self.filters = [self.filter_two]
        self.__run([import_files[1]])

    def __run(self, expected_lines):
        self.io.restore()
        self.io.install()
        self.importer.run()
        out = self.io.getoutput()

        lines = out.splitlines()
        self.assertEqual(lines, expected_lines)


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
