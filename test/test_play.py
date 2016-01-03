# -*- coding: utf-8 -*-

"""Tests for the play plugin"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from mock import patch, ANY

from test._common import unittest
from test.helper import TestHelper


class PlayPluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.load_plugins('play')
        self.item = self.add_item(title='aNiceTitle')

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    @patch('beetsplug.play.util.interactive_open')
    def test_basic(self, open_mock):
        self.run_command('play', 'title:aNiceTitle')

        open_mock.assert_called_once_with(ANY, None)
        playlist = open(open_mock.call_args[0][0][0], 'r')
        self.assertEqual(self.item.path.decode('utf-8') + '\n',
                         playlist.read().decode('utf-8'))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
