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
import _common
from _common import unittest
from helper import TestHelper, control_stdin

from beets.mediafile import MediaFile


class ImportConvertTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets(disk=True)  # Converter is threaded
        self.importer = self.create_importer()
        self.load_plugins('convert')

        self.config['convert'] = {
            'dest': os.path.join(self.temp_dir, 'convert'),
            # Append string so we can determine if the file was
            # converted
            'command': u'cp $source $dest; printf convert >> $dest',
            # Enforce running convert
            'max_bitrate': 1,
            'auto': True,
            'quiet': False,
        }

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_import_converted(self):
        self.importer.run()
        item = self.lib.items().get()
        self.assertConverted(item.path)

    def test_import_original_on_convert_error(self):
        # `false` exits with non-zero code
        self.config['convert']['command'] = u'false'
        self.importer.run()

        item = self.lib.items().get()
        self.assertIsNotNone(item)
        self.assertTrue(os.path.isfile(item.path))

    def assertConverted(self, path):
        with open(path) as f:
            f.seek(-7, os.SEEK_END)
            self.assertEqual(f.read(), 'convert',
                             '{0} was not converted'.format(path))


class ConvertCliTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets(disk=True)  # Converter is threaded
        self.album = self.add_album_fixture(ext='ogg')
        self.item = self.album.items()[0]
        self.load_plugins('convert')

        self.convert_dest = os.path.join(self.temp_dir, 'convert_dest')
        self.config['convert'] = {
            'dest': self.convert_dest,
            'paths': {'default': 'converted'},
            'format': 'mp3',
            'formats': {
                'mp3': 'cp $source $dest',
                'opus': {
                    'command': 'cp $source $dest',
                    'extension': 'ops',
                }
            }
        }

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_convert(self):
        with control_stdin('y'):
            self.run_command('convert', self.item.path)
        converted = os.path.join(self.convert_dest, 'converted.mp3')
        self.assertTrue(os.path.isfile(converted))

    def test_convert_keep_new(self):
        self.assertEqual(os.path.splitext(self.item.path)[1], '.ogg')

        with control_stdin('y'):
            self.run_command('convert', '--keep-new', self.item.path)

        self.item.load()
        self.assertEqual(os.path.splitext(self.item.path)[1], '.mp3')

    def test_format_option(self):
        with control_stdin('y'):
            self.run_command('convert', '--format', 'opus', self.item.path)
            converted = os.path.join(self.convert_dest, 'converted.ops')
        self.assertTrue(os.path.isfile(converted))

    def test_embed_album_art(self):
        self.config['convert']['embed'] = True
        image_path = os.path.join(_common.RSRC, 'image-2x3.jpg')
        self.album.artpath = image_path
        self.album.store()
        with open(os.path.join(image_path)) as f:
            image_data = f.read()

        with control_stdin('y'):
            self.run_command('convert', self.item.path)
        converted = os.path.join(self.convert_dest, 'converted.mp3')
        mediafile = MediaFile(converted)
        self.assertEqual(mediafile.images[0].data, image_data)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
