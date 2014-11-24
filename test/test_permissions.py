"""Tests for the 'permissions' plugin.
"""
from _common import unittest
from helper import TestHelper
from beetsplug.permissions import check_permissions, convert_perm


class PermissionsPluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.load_plugins('permissions')

        self.config['permissions'] = {
            'file': 777}

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def test_permissions_on_album_imported(self):
        self.importer = self.create_importer()
        self.importer.run()
        item = self.lib.items().get()
        config_perm = self.config['permissions']['file'].get()
        config_perm = convert_perm(config_perm)

        self.assertTrue(check_permissions(item.path, config_perm))
        self.assertFalse(check_permissions(item.path, convert_perm(644)))

    def test_permissions_on_item_imported(self):
        self.config['import']['singletons'] = True
        self.importer = self.create_importer()
        self.importer.run()
        item = self.lib.items().get()
        config_perm = self.config['permissions']['file'].get()
        config_perm = convert_perm(config_perm)

        self.assertTrue(check_permissions(item.path, config_perm))
        self.assertFalse(check_permissions(item.path, convert_perm(644)))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
