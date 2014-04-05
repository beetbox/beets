# This file is part of beets.
# Copyright 2014, Thomas Scholtes.
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

import os.path
from _common import unittest
from helper import TestHelper

class ImportConvertTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()
        self.importer = self.create_importer()
        self.load_plugins('convert')

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def test_import_original_on_convert_error(self):
        # `false` exits with non-zero code
        self.config['convert']['command'] = u'false'
        self.config['convert']['auto'] = True
        # Enforce running convert
        self.config['convert']['max_bitrate'] = 1
        self.config['convert']['quiet'] = False
        self.importer.run()

        item = self.lib.items().get()
        self.assertIsNotNone(item)
        self.assertTrue(os.path.isfile(item.path))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
