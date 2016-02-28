# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Jesse Weinstein
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

"""Tests for the play plugin"""

from __future__ import division, absolute_import, print_function

import os

from mock import patch, ANY

from test._common import unittest
from test.helper import TestHelper, control_stdin

from beets.ui import UserError
from beets.util import open_anything


class PlayPluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.load_plugins('play')
        self.item = self.add_item(album=u'a nice älbum', title=u'aNiceTitle')
        self.lib.add_album([self.item])
        self.open_patcher = patch('beetsplug.play.util.interactive_open')
        self.open_mock = self.open_patcher.start()
        self.config['play']['command'] = 'echo'

    def tearDown(self):
        self.open_patcher.stop()
        self.teardown_beets()
        self.unload_plugins()

    def do_test(self, args=('title:aNiceTitle',), expected_cmd='echo',
                expected_playlist=u'{}\n'):
        self.run_command('play', *args)

        self.open_mock.assert_called_once_with(ANY, expected_cmd)
        exp_playlist = expected_playlist.format(self.item.path.decode('utf-8'))
        with open(self.open_mock.call_args[0][0][0], 'r') as playlist:
            self.assertEqual(exp_playlist, playlist.read().decode('utf-8'))

    def test_basic(self):
        self.do_test()

    def test_album_option(self):
        self.do_test([u'-a', u'nice'])

    def test_args_option(self):
        self.do_test([u'-A', u'foo', u'title:aNiceTitle'], u'echo foo')

    def test_args_option_in_middle(self):
        self.config['play']['command'] = 'echo $args other'

        self.do_test([u'-A', u'foo', u'title:aNiceTitle'], u'echo foo other')

    def test_relative_to(self):
        self.config['play']['command'] = 'echo'
        self.config['play']['relative_to'] = '/something'

        self.do_test(expected_cmd='echo', expected_playlist=u'..{}\n')

    def test_use_folders(self):
        self.config['play']['command'] = None
        self.config['play']['use_folders'] = True
        self.run_command('play', '-a', 'nice')

        self.open_mock.assert_called_once_with(ANY, open_anything())
        playlist = open(self.open_mock.call_args[0][0][0], 'r')
        self.assertEqual(u'{}\n'.format(
            os.path.dirname(self.item.path.decode('utf-8'))),
            playlist.read().decode('utf-8'))

    def test_raw(self):
        self.config['play']['raw'] = True

        self.run_command(u'play', u'nice')

        self.open_mock.assert_called_once_with([self.item.path], 'echo')

    def test_not_found(self):
        self.run_command(u'play', u'not found')

        self.open_mock.assert_not_called()

    def test_warning_threshold(self):
        self.config['play']['warning_threshold'] = 1
        self.add_item(title='another NiceTitle')

        with control_stdin("a"):
            self.run_command(u'play', u'nice')

        self.open_mock.assert_not_called()

    def test_warning_threshold_backwards_compat(self):
        self.config['play']['warning_treshold'] = 1
        self.add_item(title=u'another NiceTitle')

        with control_stdin("a"):
            self.run_command(u'play', u'nice')

        self.open_mock.assert_not_called()

    def test_command_failed(self):
        self.open_mock.side_effect = OSError(u"some reason")

        with self.assertRaises(UserError):
            self.run_command(u'play', u'title:aNiceTitle')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
