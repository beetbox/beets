# -*- coding: utf-8 -*-

"""Tests for the 'permissions' plugin.
"""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

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
        self.do_test(True)

    def test_permissions_on_item_imported(self):
        self.config['import']['singletons'] = True
        self.do_test(True)

    @patch("os.chmod", Mock())
    def test_failing_to_set_permissions(self):
        self.do_test(False)

    def do_test(self, expectSuccess):
        self.importer = self.create_importer()
        self.importer.run()
        item = self.lib.items().get()

        exp_perms = {k: convert_perm(self.config['permissions'][k].get())
                     for k in ['file', 'dir']}

        self.assertPerms(item.path, convert_perm(644),
                         exp_perms['file'], expectSuccess)

        for path in dirs_in_library(self.lib.directory, item.path):
            self.assertPerms(path, convert_perm(755),
                             exp_perms['dir'], expectSuccess)

    def assertPerms(self, path, old_perms, new_perms, expectSuccess):
        for x in [(True, new_perms if expectSuccess else old_perms, '!='),
                  (False, old_perms if expectSuccess else new_perms, '==')]:
            self.assertEqual(x[0], check_permissions(path, x[1]),
                             msg='{} : {} {} {}'.format(
                path, oct(os.stat(path).st_mode), x[2], oct(x[1])))

    def test_convert_perm_from_string(self):
        self.assertEqual(convert_perm('10'), 8)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
