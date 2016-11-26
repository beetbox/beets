# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Thomas Scholtes.
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

import time
from datetime import datetime
import unittest

from test.helper import TestHelper

from beets.util.confit import ConfigValueError


class TypesPluginTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()
        self.load_plugins('types')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_integer_modify_and_query(self):
        self.config['types'] = {'myint': 'int'}
        item = self.add_item(artist=u'aaa')

        # Do not match unset values
        out = self.list(u'myint:1..3')
        self.assertEqual(u'', out)

        self.modify(u'myint=2')
        item.load()
        self.assertEqual(item['myint'], 2)

        # Match in range
        out = self.list(u'myint:1..3')
        self.assertIn('aaa', out)

    def test_album_integer_modify_and_query(self):
        self.config['types'] = {'myint': u'int'}
        album = self.add_album(albumartist=u'aaa')

        # Do not match unset values
        out = self.list_album(u'myint:1..3')
        self.assertEqual(u'', out)

        self.modify(u'-a', u'myint=2')
        album.load()
        self.assertEqual(album['myint'], 2)

        # Match in range
        out = self.list_album(u'myint:1..3')
        self.assertIn('aaa', out)

    def test_float_modify_and_query(self):
        self.config['types'] = {'myfloat': u'float'}
        item = self.add_item(artist=u'aaa')

        # Do not match unset values
        out = self.list(u'myfloat:10..0')
        self.assertEqual(u'', out)

        self.modify(u'myfloat=-9.1')
        item.load()
        self.assertEqual(item['myfloat'], -9.1)

        # Match in range
        out = self.list(u'myfloat:-10..0')
        self.assertIn('aaa', out)

    def test_bool_modify_and_query(self):
        self.config['types'] = {'mybool': u'bool'}
        true = self.add_item(artist=u'true')
        false = self.add_item(artist=u'false')
        self.add_item(artist=u'unset')

        # Do not match unset values
        out = self.list(u'mybool:true, mybool:false')
        self.assertEqual(u'', out)

        # Set true
        self.modify(u'mybool=1', u'artist:true')
        true.load()
        self.assertEqual(true['mybool'], True)

        # Set false
        self.modify(u'mybool=false', u'artist:false')
        false.load()
        self.assertEqual(false['mybool'], False)

        # Query bools
        out = self.list(u'mybool:true', u'$artist $mybool')
        self.assertEqual(u'true True', out)

        out = self.list(u'mybool:false', u'$artist $mybool')

        # Dealing with unset fields?
        # self.assertEqual('false False', out)
        # out = self.list('mybool:', '$artist $mybool')
        # self.assertIn('unset $mybool', out)

    def test_date_modify_and_query(self):
        self.config['types'] = {'mydate': u'date'}
        # FIXME parsing should also work with default time format
        self.config['time_format'] = '%Y-%m-%d'
        old = self.add_item(artist=u'prince')
        new = self.add_item(artist=u'britney')

        # Do not match unset values
        out = self.list(u'mydate:..2000')
        self.assertEqual(u'', out)

        self.modify(u'mydate=1999-01-01', u'artist:prince')
        old.load()
        self.assertEqual(old['mydate'], mktime(1999, 1, 1))

        self.modify(u'mydate=1999-12-30', u'artist:britney')
        new.load()
        self.assertEqual(new['mydate'], mktime(1999, 12, 30))

        # Match in range
        out = self.list(u'mydate:..1999-07', u'$artist $mydate')
        self.assertEqual(u'prince 1999-01-01', out)

        # FIXME some sort of timezone issue here
        # out = self.list('mydate:1999-12-30', '$artist $mydate')
        # self.assertEqual('britney 1999-12-30', out)

    def test_unknown_type_error(self):
        self.config['types'] = {'flex': 'unkown type'}
        with self.assertRaises(ConfigValueError):
            self.run_command(u'ls')

    def modify(self, *args):
        return self.run_with_output(u'modify', u'--yes', u'--nowrite',
                                    u'--nomove', *args)

    def list(self, query, fmt=u'$artist - $album - $title'):
        return self.run_with_output(u'ls', u'-f', fmt, query).strip()

    def list_album(self, query, fmt=u'$albumartist - $album - $title'):
        return self.run_with_output(u'ls', u'-a', u'-f', fmt, query).strip()


def mktime(*args):
    return time.mktime(datetime(*args).timetuple())


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
