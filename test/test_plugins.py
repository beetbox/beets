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

import shutil
import os.path
import logging
from tempfile import mkdtemp

from _common import unittest

from beets.plugins import Registry


class LogCapture(logging.Handler):

    def __init__(self, logger='beets', level=logging.DEBUG):
        super(LogCapture, self).__init__()
        self.logs = []
        self.logger = logging.getLogger(logger)
        self.logger.setLevel(level)

    def emit(self, record):
        self.logs.append((record.levelno, record.message))

    def __enter__(self):
        self.logger.addHandler(self)
        return self.logs

    def __exit__(self, exc_type, exc_value, traceback):
        self.logger.removeHandler(self)


class PluginTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_load_plugin_from_path(self):
        module_path = os.path.join(self.tmpdir, 'beets_testplug.py')
        with open(module_path, 'w') as f:
            f.write(
                'from beets.plugins import BeetsPlugin\n'
                'class TestPlugin(BeetsPlugin):\n'
                '    name = "test_plugin"'
            )
        registry = Registry(paths=[self.tmpdir])

        registry.load('testplug')
        self.assertEqual(len(registry), 1)
        self.assertEqual(registry[0].name, 'test_plugin')

    def test_load_core_plugin(self):
        registry = Registry()
        registry.load('the')
        self.assertTrue(registry[0].the)
        self.assertEqual(len(registry), 1)

    def test_plugin_not_found(self):
        registry = Registry()
        plugin_name = 'thisplugindoesnotexist'
        with LogCapture() as logs:
            registry.load(plugin_name)
        self.assertIn(
            (logging.WARN, '** plugin {0} not found'.format(plugin_name)),
            logs
        )

    def test_error_loading_plugin(self):
        module_path = os.path.join(self.tmpdir, 'beets_testplug.py')
        with open(module_path, 'w') as f:
            f.write('import this is: not valid python code')

        registry = Registry(paths=[self.tmpdir])
        with LogCapture() as logs:
            registry.load('testplug')
        self.assertIn(
            (logging.WARN, '** error loading plugin testplug'),
            logs
        )
