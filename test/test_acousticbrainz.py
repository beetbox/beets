# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Nathan Dwek.
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

"""Tests for the 'acousticbrainz' plugin.
"""

from __future__ import absolute_import, print_function

from test._common import unittest

from beetsplug.acousticbrainz import DefaultList, AcousticPlugin


class DefaultListTest(unittest.TestCase):
    def test_getitem(self):
        default_list = DefaultList('foo')
        default_value = default_list[2]
        self.assertEqual(default_value, 'foo')
        self.assertEqual(default_list, ['foo', 'foo', 'foo'])

    def test_setitem(self):
        default_list = DefaultList('foo')
        default_list[2] = 'bar'
        self.assertEqual(default_list, ['foo', 'foo', 'bar'])
        default_list[1] = 'baz'
        self.assertEqual(default_list, ['foo', 'baz', 'bar'])


class MapDataToSchemeTest(unittest.TestCase):
    def test_basic(self):
        ab = AcousticPlugin()
        data = {'key 1': 'value 1', 'key 2': 'value 2'}
        scheme = {'key 1': 'attribute 1', 'key 2': 'attribute 2'}
        mapping = set(ab._map_data_to_scheme(data, scheme))
        self.assertEqual(mapping, {('attribute 1', 'value 1'),
                                   ('attribute 2', 'value 2')})

    def test_recurse(self):
        ab = AcousticPlugin()
        data = {
            'key': 'value',
            'group': {
                'subkey': 'subvalue',
                'subgroup': {
                    'subsubkey': 'subsubvalue'
                }
            }
        }
        scheme = {
            'key': 'attribute 1',
            'group': {
                'subkey': 'attribute 2',
                'subgroup': {
                    'subsubkey': 'attribute 3'
                }
            }
        }
        mapping = set(ab._map_data_to_scheme(data, scheme))
        self.assertEqual(mapping, {('attribute 1', 'value'),
                                   ('attribute 2', 'subvalue'),
                                   ('attribute 3', 'subsubvalue')})

    def test_composite(self):
        ab = AcousticPlugin()
        data = {'key 1': 'part 1', 'key 2': 'part 2'}
        scheme = {'key 1': ('attribute', 0), 'key 2': ('attribute', 1)}
        mapping = set(ab._map_data_to_scheme(data, scheme))
        self.assertEqual(mapping, {('attribute', 'part 1 part 2')})


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
