"""Tests for the 'permissions' plugin.
"""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

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
        self.importer = self.create_importer()
        self.importer.run()
        item = self.lib.items().get()

        file_perm = self.config['permissions']['file'].get()
        file_perm = convert_perm(file_perm)

        dir_perm = self.config['permissions']['dir'].get()
        dir_perm = convert_perm(dir_perm)

        music_dirs = dirs_in_library(self.config['directory'].get(),
                                     item.path)

        self.assertTrue(check_permissions(item.path, file_perm))
        self.assertFalse(check_permissions(item.path, convert_perm(644)))

        for path in music_dirs:
            self.assertTrue(check_permissions(path, dir_perm))
            self.assertFalse(check_permissions(path, convert_perm(644)))

    def test_permissions_on_item_imported(self):
        self.config['import']['singletons'] = True
        self.importer = self.create_importer()
        self.importer.run()
        item = self.lib.items().get()

        file_perm = self.config['permissions']['file'].get()
        file_perm = convert_perm(file_perm)

        dir_perm = self.config['permissions']['dir'].get()
        dir_perm = convert_perm(dir_perm)

        music_dirs = dirs_in_library(self.config['directory'].get(),
                                     item.path)

        self.assertTrue(check_permissions(item.path, file_perm))
        self.assertFalse(check_permissions(item.path, convert_perm(644)))

        for path in music_dirs:
            self.assertTrue(check_permissions(path, dir_perm))
            self.assertFalse(check_permissions(path, convert_perm(644)))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
