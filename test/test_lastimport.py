"""Tests for the 'lastimport' plugin"""

import unittest


from beets.library import Item

from beets import config
from beetsplug import lastimport
from test import helper, _common


class LastImportPluginTest(_common.TestCase, helper.TestHelper):
    def setUp(self):
        config.clear()
        self.setup_beets()

        config["lastfm"].add({"user": "asdfg"})
        config["lastimport"].add({"per_page": 1})

        self.lastimport = lastimport.LastImportPlugin()

    def tearDown(self):
        self.teardown_beets()

    def test_e2e(self):
        item = Item(
            artist="Morcheeba",
            title="Public Displays of Affection",
        )
        id = self.lib.add(item)
        self.assertIsNone(self.lib.get_item(id).get("play_count"))

        lastimport.import_lastfm(self.lib, self.lastimport._log)
        self.assertEqual(self.lib.get_item(id).get("play_count"), "1")


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == "__main__":
    unittest.main(defaultTest="suite")
