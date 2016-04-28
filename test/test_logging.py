# -*- coding: utf-8 -*-

"""Stupid tests that ensure logging works as expected"""
from __future__ import division, absolute_import, print_function

import sys
import threading
import logging as log
from six import StringIO
import unittest

import beets.logging as blog
from beets import plugins, ui
import beetsplug
from test import _common
from test._common import TestCase
from test import helper
import six


class LoggingTest(TestCase):
    def test_logging_management(self):
        l1 = log.getLogger("foo123")
        l2 = blog.getLogger("foo123")
        self.assertEqual(l1, l2)
        self.assertEqual(l1.__class__, log.Logger)

        l3 = blog.getLogger("bar123")
        l4 = log.getLogger("bar123")
        self.assertEqual(l3, l4)
        self.assertEqual(l3.__class__, blog.BeetsLogger)
        self.assertIsInstance(l3, (blog.StrFormatLogger,
                                   blog.ThreadLocalLevelLogger))

        l5 = l3.getChild("shalala")
        self.assertEqual(l5.__class__, blog.BeetsLogger)

        l6 = blog.getLogger()
        self.assertNotEqual(l1, l6)

    def test_str_format_logging(self):
        l = blog.getLogger("baz123")
        stream = StringIO()
        handler = log.StreamHandler(stream)

        l.addHandler(handler)
        l.propagate = False

        l.warning(u"foo {0} {bar}", "oof", bar=u"baz")
        handler.flush()
        self.assertTrue(stream.getvalue(), u"foo oof baz")


class LoggingLevelTest(unittest.TestCase, helper.TestHelper):
    class DummyModule(object):
        class DummyPlugin(plugins.BeetsPlugin):
            def __init__(self):
                plugins.BeetsPlugin.__init__(self, 'dummy')
                self.import_stages = [self.import_stage]
                self.register_listener('dummy_event', self.listener)

            def log_all(self, name):
                self._log.debug(u'debug ' + name)
                self._log.info(u'info ' + name)
                self._log.warning(u'warning ' + name)

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
        self.DummyModule.DummyPlugin.listeners = None
        self.DummyModule.DummyPlugin._raw_listeners = None

    def test_command_level0(self):
        self.config['verbose'] = 0
        with helper.capture_log() as logs:
            self.run_command('dummy')
        self.assertIn(u'dummy: warning cmd', logs)
        self.assertIn(u'dummy: info cmd', logs)
        self.assertNotIn(u'dummy: debug cmd', logs)

    def test_command_level1(self):
        self.config['verbose'] = 1
        with helper.capture_log() as logs:
            self.run_command('dummy')
        self.assertIn(u'dummy: warning cmd', logs)
        self.assertIn(u'dummy: info cmd', logs)
        self.assertIn(u'dummy: debug cmd', logs)

    def test_command_level2(self):
        self.config['verbose'] = 2
        with helper.capture_log() as logs:
            self.run_command('dummy')
        self.assertIn(u'dummy: warning cmd', logs)
        self.assertIn(u'dummy: info cmd', logs)
        self.assertIn(u'dummy: debug cmd', logs)

    def test_listener_level0(self):
        self.config['verbose'] = 0
        with helper.capture_log() as logs:
            plugins.send('dummy_event')
        self.assertIn(u'dummy: warning listener', logs)
        self.assertNotIn(u'dummy: info listener', logs)
        self.assertNotIn(u'dummy: debug listener', logs)

    def test_listener_level1(self):
        self.config['verbose'] = 1
        with helper.capture_log() as logs:
            plugins.send('dummy_event')
        self.assertIn(u'dummy: warning listener', logs)
        self.assertIn(u'dummy: info listener', logs)
        self.assertNotIn(u'dummy: debug listener', logs)

    def test_listener_level2(self):
        self.config['verbose'] = 2
        with helper.capture_log() as logs:
            plugins.send('dummy_event')
        self.assertIn(u'dummy: warning listener', logs)
        self.assertIn(u'dummy: info listener', logs)
        self.assertIn(u'dummy: debug listener', logs)

    def test_import_stage_level0(self):
        self.config['verbose'] = 0
        with helper.capture_log() as logs:
            importer = self.create_importer()
            importer.run()
        self.assertIn(u'dummy: warning import_stage', logs)
        self.assertNotIn(u'dummy: info import_stage', logs)
        self.assertNotIn(u'dummy: debug import_stage', logs)

    def test_import_stage_level1(self):
        self.config['verbose'] = 1
        with helper.capture_log() as logs:
            importer = self.create_importer()
            importer.run()
        self.assertIn(u'dummy: warning import_stage', logs)
        self.assertIn(u'dummy: info import_stage', logs)
        self.assertNotIn(u'dummy: debug import_stage', logs)

    def test_import_stage_level2(self):
        self.config['verbose'] = 2
        with helper.capture_log() as logs:
            importer = self.create_importer()
            importer.run()
        self.assertIn(u'dummy: warning import_stage', logs)
        self.assertIn(u'dummy: info import_stage', logs)
        self.assertIn(u'dummy: debug import_stage', logs)


@_common.slow_test()
class ConcurrentEventsTest(TestCase, helper.TestHelper):
    """Similar to LoggingLevelTest but lower-level and focused on multiple
    events interaction. Since this is a bit heavy we don't do it in
    LoggingLevelTest.
    """
    class DummyPlugin(plugins.BeetsPlugin):
        def __init__(self, test_case):
            plugins.BeetsPlugin.__init__(self, 'dummy')
            self.register_listener('dummy_event1', self.listener1)
            self.register_listener('dummy_event2', self.listener2)
            self.lock1 = threading.Lock()
            self.lock2 = threading.Lock()
            self.test_case = test_case
            self.exc_info = None
            self.t1_step = self.t2_step = 0

        def log_all(self, name):
            self._log.debug(u'debug ' + name)
            self._log.info(u'info ' + name)
            self._log.warning(u'warning ' + name)

        def listener1(self):
            try:
                self.test_case.assertEqual(self._log.level, log.INFO)
                self.t1_step = 1
                self.lock1.acquire()
                self.test_case.assertEqual(self._log.level, log.INFO)
                self.t1_step = 2
            except Exception:
                import sys
                self.exc_info = sys.exc_info()

        def listener2(self):
            try:
                self.test_case.assertEqual(self._log.level, log.DEBUG)
                self.t2_step = 1
                self.lock2.acquire()
                self.test_case.assertEqual(self._log.level, log.DEBUG)
                self.t2_step = 2
            except Exception:
                import sys
                self.exc_info = sys.exc_info()

    def setUp(self):
        self.setup_beets(disk=True)

    def tearDown(self):
        self.teardown_beets()

    def test_concurrent_events(self):
        dp = self.DummyPlugin(self)

        def check_dp_exc():
            if dp.exc_info:
                six.reraise(dp.exc_info[1], None, dp.exc_info[2])

        try:
            dp.lock1.acquire()
            dp.lock2.acquire()
            self.assertEqual(dp._log.level, log.NOTSET)

            self.config['verbose'] = 1
            t1 = threading.Thread(target=dp.listeners['dummy_event1'][0])
            t1.start()  # blocked. t1 tested its log level
            while dp.t1_step != 1:
                check_dp_exc()
            self.assertTrue(t1.is_alive())
            self.assertEqual(dp._log.level, log.NOTSET)

            self.config['verbose'] = 2
            t2 = threading.Thread(target=dp.listeners['dummy_event2'][0])
            t2.start()  # blocked. t2 tested its log level
            while dp.t2_step != 1:
                check_dp_exc()
            self.assertTrue(t2.is_alive())
            self.assertEqual(dp._log.level, log.NOTSET)

            dp.lock1.release()  # dummy_event1 tests its log level + finishes
            while dp.t1_step != 2:
                check_dp_exc()
            t1.join(.1)
            self.assertFalse(t1.is_alive())
            self.assertTrue(t2.is_alive())
            self.assertEqual(dp._log.level, log.NOTSET)

            dp.lock2.release()  # dummy_event2 tests its log level + finishes
            while dp.t2_step != 2:
                check_dp_exc()
            t2.join(.1)
            self.assertFalse(t2.is_alive())

        except Exception:
            print(u"Alive threads:", threading.enumerate())
            if dp.lock1.locked():
                print(u"Releasing lock1 after exception in test")
                dp.lock1.release()
            if dp.lock2.locked():
                print(u"Releasing lock2 after exception in test")
                dp.lock2.release()
            print(u"Alive threads:", threading.enumerate())
            raise

    def test_root_logger_levels(self):
        """Root logger level should be shared between threads.
        """
        self.config['threaded'] = True

        blog.getLogger('beets').set_global_level(blog.WARNING)
        with helper.capture_log() as logs:
            importer = self.create_importer()
            importer.run()
        self.assertEqual(logs, [])

        blog.getLogger('beets').set_global_level(blog.INFO)
        with helper.capture_log() as logs:
            importer = self.create_importer()
            importer.run()
        for l in logs:
            self.assertIn(u"import", l)
            self.assertIn(u"album", l)

        blog.getLogger('beets').set_global_level(blog.DEBUG)
        with helper.capture_log() as logs:
            importer = self.create_importer()
            importer.run()
        self.assertIn(u"Sending event: database_change", logs)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
