# -*- coding: utf-8 -*-

"""Tests for the 'permissions' plugin.
"""
from __future__ import division, absolute_import, print_function

import os
from mock import patch, Mock

from test._common import unittest
from test.helper import TestHelper
from beetsplug.permissions import (check_permissions,
                                   convert_perm,
                                   dirs_in_library)


class PermissionsPluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.load_plugins('permissions')

        self.config['permissions'] = {
            'file': 777,
            'dir': 777}

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def test_permissions_on_album_imported(self):
        self.do_thing(True)

    def test_permissions_on_item_imported(self):
        self.config['import']['singletons'] = True
        self.do_thing(True)

    @patch("os.chmod", Mock())
    def test_failing_to_set_permissions(self):
        self.do_thing(False)

    def do_thing(self, expectSuccess):
        def get_stat(v):
            return os.stat(
                os.path.join(self.temp_dir, 'import', *v)).st_mode & 0o777
        self.importer = self.create_importer()
        typs = ['file', 'dir']
        self.exp_perms = {
            True: {k: convert_perm(self.config['permissions'][k].get())
                   for k in typs},
            False: {k: get_stat(v)
                    for (k, v) in zip(typs, (('album 0', 'track 0.mp3'), ()))}}

        self.importer.run()
        item = self.lib.items().get()

        self.assertPerms(item.path, 'file', expectSuccess)

        for path in dirs_in_library(self.lib.directory, item.path):
            self.assertPerms(path, 'dir', expectSuccess)

    def assertPerms(self, path, typ, expectSuccess):
        for x in [(True, self.exp_perms[expectSuccess][typ], '!='),
                  (False, self.exp_perms[not expectSuccess][typ], '==')]:
            self.assertEqual(x[0], check_permissions(path, x[1]),
                             msg=u'{} : {} {} {}'.format(
                path, oct(os.stat(path).st_mode), x[2], oct(x[1])))

    def test_convert_perm_from_string(self):
        self.assertEqual(convert_perm('10'), 8)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
