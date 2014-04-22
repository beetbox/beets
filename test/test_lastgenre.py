# This file is part of beets.
# Copyright 2014, Fabrice Laporte.
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

"""Tests for the 'lastgenre' plugin."""

from _common import unittest
from beetsplug import lastgenre
from beets import config

class LastGenrePluginTest(unittest.TestCase):
    def setUp(self):
        """Set up configuration"""
        lyrics.LastGenrePlugin()

    def _setup_config(self, whitelist=set(), branches=None, count=1):
        config['lastgenre']['whitelist'] = whitelist
        if branches:
            config['lastgenre']['branches'] = branches
            config['lastgenre']['c14n'] = True
        else:
            config['lastgenre']['c14n'] = False
        config['lastgenre']['count'] = count

    def test_c14n():
        _setup_config(set('blues'),
                      [['blues'],
                       ['blues', 'country blues'],
                       ['blues', 'country blues', 'delta blues']])

        self.assertEqual(lastgenre._strings_to_genre(['delta blues']),
                         'blues')


