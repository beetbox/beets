# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2017, Dorian Soergel
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

"""Tests for the 'parentwork' plugin."""

from __future__ import division, absolute_import, print_function

import unittest
from test.helper import TestHelper
from beetsplug import parentwork


class ParentWorkPluginFunctional(unittest.TestCase, TestHelper):
    def setUp(self):
        """Set up configuration"""
        self.setup_beets()
        self.load_plugins('parentwork')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def _pw_add_item(self, artist, title, work_id, parent_work=None,
                     parent_work_disambig=None, parent_composer=None,
                     parent_work_id=None):
        return self.add_item(artist=artist,
                             title=title,
                             work_id=work_id,
                             parent_work=parent_work,
                             parent_work_disambig=parent_work_disambig,
                             parent_composer=parent_composer,
                             parent_composer_sort=parent_work_id)

    def _pw_set_config(self, force):
        self.config['parentwork']['force'] = force
        
    def test_father_work(self):
        work_id = u'2e4a3668-458d-3b2a-8be2-0b08e0d8243a'
        self.assertEqual(u'f04b42df-7251-4d86-a5ee-67cfa49580d1',
                         parentwork.work_father(work_id))
        self.assertEqual(u'45afb3b2-18ac-4187-bc72-beb1b1c194ba',
                         parentwork.work_parent(work_id))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
