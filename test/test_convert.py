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
from pathlib import Path
from _common import unittest
from helper import TestHelper, controlStdin

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

class ImportCliTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()
        self.item, = self.add_item_fixtures(ext='ogg')
        self.load_plugins('convert')

        self.convert_dest = Path(self.temp_dir) / 'convert_dest'
        self.config['convert']['dest'] = str(self.convert_dest)
        self.config['convert']['command'] = u'cp $source $dest'
        self.config['convert']['paths']['default'] = u'converted'

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def test_convert(self):
        with controlStdin('y'):
            self.run_command('convert', self.item.path)
        converted = Path(self.convert_dest) / 'converted.mp3'
        self.assertTrue(converted.is_file())

    def test_convert_keep_new(self):
        self.assertEqual(Path(self.item.path).suffix, '.ogg')

        with controlStdin('y'):
            self.run_command('convert', '--keep-new', self.item.path)

        self.item.load()
        self.assertEqual(Path(self.item.path).suffix, '.mp3')

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
