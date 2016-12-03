# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Tests the TerminalImportSession. The tests are the same as in the

test_importer module. But here the test importer inherits from
``TerminalImportSession``. So we test this class, too.
"""

from __future__ import division, absolute_import, print_function
import unittest

from test._common import DummyIO
from test import test_importer
from beets.ui.commands import TerminalImportSession
from beets import importer
from beets import config
import six


class TestTerminalImportSession(TerminalImportSession):

    def __init__(self, *args, **kwargs):
        self.io = kwargs.pop('io')
        super(TestTerminalImportSession, self).__init__(*args, **kwargs)
        self._choices = []

    default_choice = importer.action.APPLY

    def add_choice(self, choice):
        self._choices.append(choice)

    def clear_choices(self):
        self._choices = []

    def choose_match(self, task):
        self._add_choice_input()
        return super(TestTerminalImportSession, self).choose_match(task)

    def choose_item(self, task):
        self._add_choice_input()
        return super(TestTerminalImportSession, self).choose_item(task)

    def _add_choice_input(self):
        try:
            choice = self._choices.pop(0)
        except IndexError:
            choice = self.default_choice

        if choice == importer.action.APPLY:
            self.io.addinput(u'A')
        elif choice == importer.action.ASIS:
            self.io.addinput(u'U')
        elif choice == importer.action.ALBUMS:
            self.io.addinput(u'G')
        elif choice == importer.action.TRACKS:
            self.io.addinput(u'T')
        elif choice == importer.action.SKIP:
            self.io.addinput(u'S')
        elif isinstance(choice, int):
            self.io.addinput(u'M')
            self.io.addinput(six.text_type(choice))
            self._add_choice_input()
        else:
            raise Exception(u'Unknown choice %s' % choice)


class TerminalImportSessionSetup(object):
    """Overwrites test_importer.ImportHelper to provide a terminal importer
    """

    def _setup_import_session(self, import_dir=None, delete=False,
                              threaded=False, copy=True, singletons=False,
                              move=False, autotag=True):
        config['import']['copy'] = copy
        config['import']['delete'] = delete
        config['import']['timid'] = True
        config['threaded'] = False
        config['import']['singletons'] = singletons
        config['import']['move'] = move
        config['import']['autotag'] = autotag
        config['import']['resume'] = False

        if not hasattr(self, 'io'):
            self.io = DummyIO()
        self.io.install()
        self.importer = TestTerminalImportSession(
            self.lib, loghandler=None, query=None, io=self.io,
            paths=[import_dir or self.import_dir],
        )


class NonAutotaggedImportTest(TerminalImportSessionSetup,
                              test_importer.NonAutotaggedImportTest):
    pass


class ImportTest(TerminalImportSessionSetup,
                 test_importer.ImportTest):
    pass


class ImportSingletonTest(TerminalImportSessionSetup,
                          test_importer.ImportSingletonTest):
    pass


class ImportTracksTest(TerminalImportSessionSetup,
                       test_importer.ImportTracksTest):
    pass


class ImportCompilationTest(TerminalImportSessionSetup,
                            test_importer.ImportCompilationTest):
    pass


class ImportExistingTest(TerminalImportSessionSetup,
                         test_importer.ImportExistingTest):
    pass


class ChooseCandidateTest(TerminalImportSessionSetup,
                          test_importer.ChooseCandidateTest):
    pass


class GroupAlbumsImportTest(TerminalImportSessionSetup,
                            test_importer.GroupAlbumsImportTest):
    pass


class GlobalGroupAlbumsImportTest(TerminalImportSessionSetup,
                                  test_importer.GlobalGroupAlbumsImportTest):
    pass


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
