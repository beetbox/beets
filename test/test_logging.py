"""Stupid tests that ensure logging works as expected"""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import sys
import logging as log
from StringIO import StringIO

import beets.logging as blog
from beets import plugins, ui
import beetsplug
from test._common import unittest, TestCase
from test import helper


class LoggingTest(TestCase):
    def test_logging_management(self):
        l1 = log.getLogger("foo123")
        l2 = blog.getLogger("foo123")
        self.assertEqual(l1, l2)
        self.assertEqual(l1.__class__, log.Logger)

        l3 = blog.getLogger("bar123")
        l4 = log.getLogger("bar123")
        self.assertEqual(l3, l4)
        self.assertEqual(l3.__class__, blog.StrFormatLogger)

        l5 = l3.getChild("shalala")
        self.assertEqual(l5.__class__, blog.StrFormatLogger)

    def test_str_format_logging(self):
        l = blog.getLogger("baz123")
        stream = StringIO()
        handler = log.StreamHandler(stream)

        l.addHandler(handler)
        l.propagate = False

        l.warning("foo {0} {bar}", "oof", bar="baz")
        handler.flush()
        self.assertTrue(stream.getvalue(), "foo oof baz")


class LoggingLevelTest(unittest.TestCase, helper.TestHelper):
    class DummyModule(object):
        class DummyPlugin(plugins.BeetsPlugin):
            def __init__(self):
                plugins.BeetsPlugin.__init__(self, 'dummy')
                self.import_stages = [self.import_stage]
                self.register_listener('dummy_event', self.listener)

            def log_all(self, name):
                self._log.debug('debug ' + name)
                self._log.info('info ' + name)
                self._log.warning('warning ' + name)

            def commands(self):
                cmd = ui.Subcommand('dummy')
                cmd.func = lambda _, __, ___: self.log_all('cmd')
                return (cmd,)

            def import_stage(self, session, task):
                self.log_all('import_stage')

            def listener(self):
                self.log_all('listener')

    def setUp(self):
        sys.modules['beetsplug.dummy'] = self.DummyModule
        beetsplug.dummy = self.DummyModule
        self.setup_beets()
        self.load_plugins('dummy')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()
        del beetsplug.dummy
        sys.modules.pop('beetsplug.dummy')

    def test_command_logging(self):
        self.config['verbose'] = 0
        with helper.capture_log() as logs:
            self.run_command('dummy')
        self.assertIn('dummy: warning cmd', logs)
        self.assertIn('dummy: info cmd', logs)
        self.assertNotIn('dummy: debug cmd', logs)

        for level in (1, 2):
            self.config['verbose'] = level
            with helper.capture_log() as logs:
                self.run_command('dummy')
            self.assertIn('dummy: warning cmd', logs)
            self.assertIn('dummy: info cmd', logs)
            self.assertIn('dummy: debug cmd', logs)

    def test_listener_logging(self):
        self.config['verbose'] = 0
        with helper.capture_log() as logs:
            plugins.send('dummy_event')
        self.assertIn('dummy: warning listener', logs)
        self.assertNotIn('dummy: info listener', logs)
        self.assertNotIn('dummy: debug listener', logs)

        self.config['verbose'] = 1
        with helper.capture_log() as logs:
            plugins.send('dummy_event')
        self.assertIn('dummy: warning listener', logs)
        self.assertIn('dummy: info listener', logs)
        self.assertNotIn('dummy: debug listener', logs)

        self.config['verbose'] = 2
        with helper.capture_log() as logs:
            plugins.send('dummy_event')
        self.assertIn('dummy: warning listener', logs)
        self.assertIn('dummy: info listener', logs)
        self.assertIn('dummy: debug listener', logs)

    def test_import_stage_logging(self):
        self.config['verbose'] = 0
        with helper.capture_log() as logs:
            importer = self.create_importer()
            importer.run()
        self.assertIn('dummy: warning import_stage', logs)
        self.assertNotIn('dummy: info import_stage', logs)
        self.assertNotIn('dummy: debug import_stage', logs)

        self.config['verbose'] = 1
        with helper.capture_log() as logs:
            importer = self.create_importer()
            importer.run()
        self.assertIn('dummy: warning import_stage', logs)
        self.assertIn('dummy: info import_stage', logs)
        self.assertNotIn('dummy: debug import_stage', logs)

        self.config['verbose'] = 2
        with helper.capture_log() as logs:
            importer = self.create_importer()
            importer.run()
        self.assertIn('dummy: warning import_stage', logs)
        self.assertIn('dummy: info import_stage', logs)
        self.assertIn('dummy: debug import_stage', logs)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
