# This file is part of beets.
# Copyright 2015, Thomas Scholtes.
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

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import time
from datetime import datetime

from test._common import unittest
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
        item = self.add_item(artist='aaa')

        # Do not match unset values
        out = self.list('myint:1..3')
        self.assertEqual('', out)

        self.modify('myint=2')
        item.load()
        self.assertEqual(item['myint'], 2)

        # Match in range
        out = self.list('myint:1..3')
        self.assertIn(b'aaa', out)

    def test_album_integer_modify_and_query(self):
        self.config['types'] = {'myint': 'int'}
        album = self.add_album(albumartist='aaa')

        # Do not match unset values
        out = self.list_album('myint:1..3')
        self.assertEqual('', out)

        self.modify('-a', 'myint=2')
        album.load()
        self.assertEqual(album['myint'], 2)

        # Match in range
        out = self.list_album('myint:1..3')
        self.assertIn(b'aaa', out)

    def test_float_modify_and_query(self):
        self.config['types'] = {'myfloat': 'float'}
        item = self.add_item(artist='aaa')

        self.modify('myfloat=-9.1')
        item.load()
        self.assertEqual(item['myfloat'], -9.1)

        # Match in range
        out = self.list('myfloat:-10..0')
        self.assertIn(b'aaa', out)

    def test_bool_modify_and_query(self):
        self.config['types'] = {'mybool': 'bool'}
        true = self.add_item(artist='true')
        false = self.add_item(artist='false')
        self.add_item(artist='unset')

        # Set true
        self.modify('mybool=1', 'artist:true')
        true.load()
        self.assertEqual(true['mybool'], True)

        # Set false
        self.modify('mybool=false', 'artist:false')
        false.load()
        self.assertEqual(false['mybool'], False)

        # Query bools
        out = self.list('mybool:true', '$artist $mybool')
        self.assertEqual('true True', out)

        out = self.list('mybool:false', '$artist $mybool')

        # Dealing with unset fields?
        # self.assertEqual('false False', out)
        # out = self.list('mybool:', '$artist $mybool')
        # self.assertIn('unset $mybool', out)

    def test_date_modify_and_query(self):
        self.config['types'] = {'mydate': 'date'}
        # FIXME parsing should also work with default time format
        self.config['time_format'] = '%Y-%m-%d'
        old = self.add_item(artist='prince')
        new = self.add_item(artist='britney')

        self.modify('mydate=1999-01-01', 'artist:prince')
        old.load()
        self.assertEqual(old['mydate'], mktime(1999, 01, 01))

        self.modify('mydate=1999-12-30', 'artist:britney')
        new.load()
        self.assertEqual(new['mydate'], mktime(1999, 12, 30))

        # Match in range
        out = self.list('mydate:..1999-07', '$artist $mydate')
        self.assertEqual('prince 1999-01-01', out)

        # FIXME some sort of timezone issue here
        # out = self.list('mydate:1999-12-30', '$artist $mydate')
        # self.assertEqual('britney 1999-12-30', out)

    def test_unknown_type_error(self):
        self.config['types'] = {'flex': 'unkown type'}
        with self.assertRaises(ConfigValueError):
            self.run_command('ls')

    def modify(self, *args):
        return self.run_with_output('modify', '--yes', '--nowrite',
                                    '--nomove', *args)

    def list(self, query, fmt='$artist - $album - $title'):
        return self.run_with_output('ls', '-f', fmt, query).strip()

    def list_album(self, query, fmt='$albumartist - $album - $title'):
        return self.run_with_output('ls', '-a', '-f', fmt, query).strip()


def mktime(*args):
    return time.mktime(datetime(*args).timetuple())


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
