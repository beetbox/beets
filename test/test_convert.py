# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Thomas Scholtes.
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

from __future__ import division, absolute_import, print_function

import re
import os.path
from test import _common
from test._common import unittest
from test import helper
from test.helper import control_stdin

from beets.mediafile import MediaFile
from beets import util


class TestHelper(helper.TestHelper):

    def tagged_copy_cmd(self, tag):
        """Return a conversion command that copies files and appends
        `tag` to the copy.
        """
        if re.search('[^a-zA-Z0-9]', tag):
            raise ValueError(u"tag '{0}' must only contain letters and digits"
                             .format(tag))
        # FIXME This is not portable. For windows we need to use our own
        # python script that performs the same task.
        return u'sh -c "cp \'$source\' \'$dest\'; ' \
               u'printf {0} >> \'$dest\'"'.format(tag)

    def assertFileTag(self, path, tag):  # noqa
        """Assert that the path is a file and the files content ends with `tag`.
        """
        self.assertTrue(os.path.isfile(path),
                        u'{0} is not a file'.format(path))
        with open(path) as f:
            f.seek(-len(tag), os.SEEK_END)
            self.assertEqual(f.read(), tag,
                             u'{0} is not tagged with {1}'.format(path, tag))

    def assertNoFileTag(self, path, tag):  # noqa
        """Assert that the path is a file and the files content does not
        end with `tag`.
        """
        self.assertTrue(os.path.isfile(path),
                        u'{0} is not a file'.format(path))
        with open(path) as f:
            f.seek(-len(tag), os.SEEK_END)
            self.assertNotEqual(f.read(), tag,
                                u'{0} is unexpectedly tagged with {1}'
                                .format(path, tag))


@_common.slow_test()
class ImportConvertTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets(disk=True)  # Converter is threaded
        self.importer = self.create_importer()
        self.load_plugins('convert')

        self.config['convert'] = {
            'dest': os.path.join(self.temp_dir, 'convert'),
            'command': self.tagged_copy_cmd('convert'),
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
        self.assertFileTag(item.path, 'convert')

    def test_import_original_on_convert_error(self):
        # `false` exits with non-zero code
        self.config['convert']['command'] = u'false'
        self.importer.run()

        item = self.lib.items().get()
        self.assertIsNotNone(item)
        self.assertTrue(os.path.isfile(item.path))


@_common.slow_test()
class ConvertCliTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets(disk=True)  # Converter is threaded
        self.album = self.add_album_fixture(ext='ogg')
        self.item = self.album.items()[0]
        self.load_plugins('convert')

        self.convert_dest = util.bytestring_path(
            os.path.join(self.temp_dir, 'convert_dest')
        )
        self.config['convert'] = {
            'dest': self.convert_dest,
            'paths': {'default': 'converted'},
            'format': 'mp3',
            'formats': {
                'mp3': self.tagged_copy_cmd('mp3'),
                'opus': {
                    'command': self.tagged_copy_cmd('opus'),
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
        self.assertFileTag(converted, 'mp3')

    def test_convert_with_auto_confirmation(self):
        self.run_command('convert', '--yes', self.item.path)
        converted = os.path.join(self.convert_dest, 'converted.mp3')
        self.assertFileTag(converted, 'mp3')

    def test_rejecet_confirmation(self):
        with control_stdin('n'):
            self.run_command('convert', self.item.path)
        converted = os.path.join(self.convert_dest, 'converted.mp3')
        self.assertFalse(os.path.isfile(converted))

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
        self.assertFileTag(converted, 'opus')

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

    def test_skip_existing(self):
        converted = os.path.join(self.convert_dest, 'converted.mp3')
        self.touch(converted, content='XXX')
        self.run_command('convert', '--yes', self.item.path)
        with open(converted, 'r') as f:
            self.assertEqual(f.read(), 'XXX')

    def test_pretend(self):
        self.run_command('convert', '--pretend', self.item.path)
        converted = os.path.join(self.convert_dest, 'converted.mp3')
        self.assertFalse(os.path.exists(converted))


@_common.slow_test()
class NeverConvertLossyFilesTest(unittest.TestCase, TestHelper):
    """Test the effect of the `never_convert_lossy_files` option.
    """

    def setUp(self):
        self.setup_beets(disk=True)  # Converter is threaded
        self.load_plugins('convert')

        self.convert_dest = os.path.join(self.temp_dir, 'convert_dest')
        self.config['convert'] = {
            'dest': self.convert_dest,
            'paths': {'default': 'converted'},
            'never_convert_lossy_files': True,
            'format': 'mp3',
            'formats': {
                'mp3': self.tagged_copy_cmd('mp3'),
            }
        }

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_transcode_from_lossles(self):
        [item] = self.add_item_fixtures(ext='flac')
        with control_stdin('y'):
            self.run_command('convert', item.path)
        converted = os.path.join(self.convert_dest, 'converted.mp3')
        self.assertFileTag(converted, 'mp3')

    def test_transcode_from_lossy(self):
        self.config['convert']['never_convert_lossy_files'] = False
        [item] = self.add_item_fixtures(ext='ogg')
        with control_stdin('y'):
            self.run_command('convert', item.path)
        converted = os.path.join(self.convert_dest, 'converted.mp3')
        self.assertFileTag(converted, 'mp3')

    def test_transcode_from_lossy_prevented(self):
        [item] = self.add_item_fixtures(ext='ogg')
        with control_stdin('y'):
            self.run_command('convert', item.path)
        converted = os.path.join(self.convert_dest, 'converted.ogg')
        self.assertNoFileTag(converted, 'mp3')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
