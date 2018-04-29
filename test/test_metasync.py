# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Tom Jaspers.
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

from __future__ import division, absolute_import, print_function

import os
import platform
import time
from datetime import datetime
from beets.library import Item
from beets.util import py3_path
import unittest

from test import _common
from test.helper import TestHelper


def _parsetime(s):
    return time.mktime(datetime.strptime(s, '%Y-%m-%d %H:%M:%S').timetuple())


def _is_windows():
    return platform.system() == "Windows"


class MetaSyncTest(_common.TestCase, TestHelper):
    itunes_library_unix = os.path.join(_common.RSRC,
                                       b'itunes_library_unix.xml')
    itunes_library_windows = os.path.join(_common.RSRC,
                                          b'itunes_library_windows.xml')

    def setUp(self):
        self.setup_beets()
        self.load_plugins('metasync')

        self.config['metasync']['source'] = 'itunes'

        if _is_windows():
            self.config['metasync']['itunes']['library'] = \
                py3_path(self.itunes_library_windows)
        else:
            self.config['metasync']['itunes']['library'] = \
                py3_path(self.itunes_library_unix)

        self._set_up_data()

    def _set_up_data(self):
        items = [_common.item() for _ in range(2)]

        items[0].title = 'Tessellate'
        items[0].artist = 'alt-J'
        items[0].albumartist = 'alt-J'
        items[0].album = 'An Awesome Wave'
        items[0].itunes_rating = 60

        items[1].title = 'Breezeblocks'
        items[1].artist = 'alt-J'
        items[1].albumartist = 'alt-J'
        items[1].album = 'An Awesome Wave'

        if _is_windows():
            items[0].path = \
                u'G:\\Music\\Alt-J\\An Awesome Wave\\03 Tessellate.mp3'
            items[1].path = \
                u'G:\\Music\\Alt-J\\An Awesome Wave\\04 Breezeblocks.mp3'
        else:
            items[0].path = u'/Music/Alt-J/An Awesome Wave/03 Tessellate.mp3'
            items[1].path = u'/Music/Alt-J/An Awesome Wave/04 Breezeblocks.mp3'

        for item in items:
            self.lib.add(item)

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_load_item_types(self):
        # This test also verifies that the MetaSources have loaded correctly
        self.assertIn('amarok_score', Item._types)
        self.assertIn('itunes_rating', Item._types)

    def test_pretend_sync_from_itunes(self):
        out = self.run_with_output('metasync', '-p')

        self.assertIn('itunes_rating: 60 -> 80', out)
        self.assertIn('itunes_rating: 100', out)
        self.assertIn('itunes_playcount: 31', out)
        self.assertIn('itunes_skipcount: 3', out)
        self.assertIn('itunes_lastplayed: 2015-05-04 12:20:51', out)
        self.assertIn('itunes_lastskipped: 2015-02-05 15:41:04', out)
        self.assertEqual(self.lib.items()[0].itunes_rating, 60)

    def test_sync_from_itunes(self):
        self.run_command('metasync')

        self.assertEqual(self.lib.items()[0].itunes_rating, 80)
        self.assertEqual(self.lib.items()[0].itunes_playcount, 0)
        self.assertEqual(self.lib.items()[0].itunes_skipcount, 3)
        self.assertFalse(hasattr(self.lib.items()[0], 'itunes_lastplayed'))
        self.assertEqual(self.lib.items()[0].itunes_lastskipped,
                         _parsetime('2015-02-05 15:41:04'))

        self.assertEqual(self.lib.items()[1].itunes_rating, 100)
        self.assertEqual(self.lib.items()[1].itunes_playcount, 31)
        self.assertEqual(self.lib.items()[1].itunes_skipcount, 0)
        self.assertEqual(self.lib.items()[1].itunes_lastplayed,
                         _parsetime('2015-05-04 12:20:51'))
        self.assertFalse(hasattr(self.lib.items()[1], 'itunes_lastskipped'))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
