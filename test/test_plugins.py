# This file is part of beets.
# Copyright 2015, Thomas Scholtes.
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

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import os
from mock import patch
import shutil

from beets.importer import SingletonImportTask, SentinelImportTask, \
    ArchiveImportTask
from beets import plugins, config
from beets.library import Item
from beets.dbcore import types
from beets.mediafile import MediaFile
from test.test_importer import ImportHelper
from test._common import unittest, RSRC
from test import helper


class TestHelper(helper.TestHelper):

    def setup_plugin_loader(self):
        # FIXME the mocking code is horrific, but this is the lowest and
        # earliest level of the plugin mechanism we can hook into.
        self.load_plugins()
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
        self.event_listener_plugin = EventListenerPlugin()
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


class EventsTest(unittest.TestCase, ImportHelper, TestHelper):

    def setUp(self):
        self.setup_plugin_loader()
        self.setup_beets()
        self.__create_import_dir(2)
        config['import']['pretend'] = True

    def tearDown(self):
        self.teardown_plugin_loader()
        self.teardown_beets()

    def __copy_file(self, dest_path, metadata):
        # Copy files
        resource_path = os.path.join(RSRC, 'full.mp3')
        shutil.copy(resource_path, dest_path)
        medium = MediaFile(dest_path)
        # Set metadata
        for attr in metadata:
            setattr(medium, attr, metadata[attr])
        medium.save()

    def __create_import_dir(self, count):
        self.import_dir = os.path.join(self.temp_dir, 'testsrcdir')
        if os.path.isdir(self.import_dir):
            shutil.rmtree(self.import_dir)

        self.album_path = os.path.join(self.import_dir, 'album')
        os.makedirs(self.album_path)

        metadata = {
            'artist': 'Tag Artist',
            'album':  'Tag Album',
            'albumartist':  None,
            'mb_trackid': None,
            'mb_albumid': None,
            'comp': None
        }
        self.file_paths = []
        for i in range(count):
            metadata['track'] = i + 1
            metadata['title'] = 'Tag Title Album %d' % (i + 1)
            dest_path = os.path.join(self.album_path,
                                     '%02d - track.mp3' % (i + 1))
            self.__copy_file(dest_path, metadata)
            self.file_paths.append(dest_path)

    def test_import_task_created(self):
        import_files = [self.import_dir]
        self._setup_import_session(singletons=False)
        self.importer.paths = import_files

        with helper.capture_log() as logs:
            self.importer.run()
        self.unload_plugins()

        # Exactly one event should have been imported (for the album).
        # Sentinels do not get emitted.
        self.assertEqual(logs.count('Sending event: import_task_created'), 1)

        logs = [line for line in logs if not line.startswith('Sending event:')]
        self.assertEqual(logs, [
            'Album: {0}'.format(os.path.join(self.import_dir, 'album')),
            '  {0}'.format(self.file_paths[0]),
            '  {0}'.format(self.file_paths[1]),
        ])

    def test_import_task_created_with_plugin(self):
        class ToSingletonPlugin(plugins.BeetsPlugin):
            def __init__(self):
                super(ToSingletonPlugin, self).__init__()

                self.register_listener('import_task_created',
                                       self.import_task_created_event)

            def import_task_created_event(self, session, task):
                if isinstance(task, SingletonImportTask) \
                        or isinstance(task, SentinelImportTask)\
                        or isinstance(task, ArchiveImportTask):
                    return task

                new_tasks = []
                for item in task.items:
                    new_tasks.append(SingletonImportTask(task.toppath, item))

                return new_tasks

        to_singleton_plugin = ToSingletonPlugin
        self.register_plugin(to_singleton_plugin)

        import_files = [self.import_dir]
        self._setup_import_session(singletons=False)
        self.importer.paths = import_files

        with helper.capture_log() as logs:
            self.importer.run()
        self.unload_plugins()

        # Exactly one event should have been imported (for the album).
        # Sentinels do not get emitted.
        self.assertEqual(logs.count('Sending event: import_task_created'), 1)

        logs = [line for line in logs if not line.startswith('Sending event:')]
        self.assertEqual(logs, [
            'Singleton: {0}'.format(self.file_paths[0]),
            'Singleton: {0}'.format(self.file_paths[1]),
        ])


class HelpersTest(unittest.TestCase):

    def test_sanitize_choices(self):
        self.assertEqual(plugins.sanitize_choices(['A', 'Z'], ('A', 'B')),
                         ['A'])
        self.assertEqual(plugins.sanitize_choices(['A', 'A'], ('A')), ['A'])
        self.assertEqual(plugins.sanitize_choices(['D', '*', 'A'],
                         ('A', 'B', 'C', 'D')), ['D', 'B', 'C', 'A'])


class ListenersTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_plugin_loader()

    def tearDown(self):
        self.teardown_plugin_loader()
        self.teardown_beets()

    def test_register(self):

        class DummyPlugin(plugins.BeetsPlugin):
            def __init__(self):
                super(DummyPlugin, self).__init__()
                self.register_listener('cli_exit', self.dummy)
                self.register_listener('cli_exit', self.dummy)

            def dummy(self):
                pass

        d = DummyPlugin()
        self.assertEqual(DummyPlugin._raw_listeners['cli_exit'], [d.dummy])

        d2 = DummyPlugin()
        self.assertEqual(DummyPlugin._raw_listeners['cli_exit'],
                         [d.dummy, d2.dummy])

        d.register_listener('cli_exit', d2.dummy)
        self.assertEqual(DummyPlugin._raw_listeners['cli_exit'],
                         [d.dummy, d2.dummy])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
