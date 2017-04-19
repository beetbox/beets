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

import unittest
from mock import patch, ANY

from test.helper import TestHelper, control_stdin

from beets.ui import UserError
from beets.util import open_anything


@patch('beetsplug.play.util.interactive_open')
class PlayPluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.load_plugins('play')
        self.item = self.add_item(album=u'a nice älbum', title=u'aNiceTitle')
        self.lib.add_album([self.item])
        self.config['play']['command'] = 'echo'

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def run_and_assert(self, open_mock, args=('title:aNiceTitle',),
                       expected_cmd='echo', expected_playlist=None):
        self.run_command('play', *args)

        open_mock.assert_called_once_with(ANY, expected_cmd)
        expected_playlist = expected_playlist or self.item.path.decode('utf-8')
        exp_playlist = expected_playlist + u'\n'
        with open(open_mock.call_args[0][0][0], 'rb') as playlist:
            self.assertEqual(exp_playlist, playlist.read().decode('utf-8'))

    def test_basic(self, open_mock):
        self.run_and_assert(open_mock)

    def test_album_option(self, open_mock):
        self.run_and_assert(open_mock, [u'-a', u'nice'])

    def test_args_option(self, open_mock):
        self.run_and_assert(
            open_mock, [u'-A', u'foo', u'title:aNiceTitle'], u'echo foo')

    def test_args_option_in_middle(self, open_mock):
        self.config['play']['command'] = 'echo $args other'

        self.run_and_assert(
            open_mock, [u'-A', u'foo', u'title:aNiceTitle'], u'echo foo other')

    def test_unset_args_option_in_middle(self, open_mock):
        self.config['play']['command'] = 'echo $args other'

        self.run_and_assert(
            open_mock, [u'title:aNiceTitle'], u'echo other')

    def test_relative_to(self, open_mock):
        self.config['play']['command'] = 'echo'
        self.config['play']['relative_to'] = '/something'

        path = os.path.relpath(self.item.path, b'/something')
        playlist = path.decode('utf-8')
        self.run_and_assert(
            open_mock, expected_cmd='echo', expected_playlist=playlist)

    def test_use_folders(self, open_mock):
        self.config['play']['command'] = None
        self.config['play']['use_folders'] = True
        self.run_command('play', '-a', 'nice')

        open_mock.assert_called_once_with(ANY, open_anything())
        with open(open_mock.call_args[0][0][0], 'rb') as f:
            playlist = f.read().decode('utf-8')
        self.assertEqual(u'{}\n'.format(
            os.path.dirname(self.item.path.decode('utf-8'))),
            playlist)

    def test_raw(self, open_mock):
        self.config['play']['raw'] = True

        self.run_command(u'play', u'nice')

        open_mock.assert_called_once_with([self.item.path], 'echo')

    def test_not_found(self, open_mock):
        self.run_command(u'play', u'not found')

        open_mock.assert_not_called()

    def test_warning_threshold(self, open_mock):
        self.config['play']['warning_threshold'] = 1
        self.add_item(title='another NiceTitle')

        with control_stdin("a"):
            self.run_command(u'play', u'nice')

        open_mock.assert_not_called()

    def test_skip_warning_threshold_bypass(self, open_mock):
        self.config['play']['warning_threshold'] = 1
        self.other_item = self.add_item(title='another NiceTitle')

        expected_playlist = u'{0}\n{1}'.format(
            self.item.path.decode('utf-8'),
            self.other_item.path.decode('utf-8'))

        with control_stdin("a"):
            self.run_and_assert(
                open_mock,
                [u'-y', u'NiceTitle'],
                expected_playlist=expected_playlist)

    def test_command_failed(self, open_mock):
        open_mock.side_effect = OSError(u"some reason")

        with self.assertRaises(UserError):
            self.run_command(u'play', u'title:aNiceTitle')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
