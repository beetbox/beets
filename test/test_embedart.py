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

import os.path
import shutil
from mock import patch
import tempfile

from test import _common
from test._common import unittest
from test.helper import TestHelper

from beets.mediafile import MediaFile
from beets import config, logging, ui
from beets.util import syspath
from beets.util.artresizer import ArtResizer
from beets import art


def require_artresizer_compare(test):

    def wrapper(*args, **kwargs):
        if not ArtResizer.shared.can_compare:
            raise unittest.SkipTest()
        else:
            return test(*args, **kwargs)

    wrapper.__name__ = test.__name__
    return wrapper


class EmbedartCliTest(_common.TestCase, TestHelper):

    small_artpath = os.path.join(_common.RSRC, 'image-2x3.jpg')
    abbey_artpath = os.path.join(_common.RSRC, 'abbey.jpg')
    abbey_similarpath = os.path.join(_common.RSRC, 'abbey-similar.jpg')
    abbey_differentpath = os.path.join(_common.RSRC, 'abbey-different.jpg')

    def setUp(self):
        self.setup_beets()  # Converter is threaded
        self.load_plugins('embedart')

    def _setup_data(self, artpath=None):
        if not artpath:
            artpath = self.small_artpath
        with open(syspath(artpath)) as f:
            self.image_data = f.read()

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_embed_art_from_file(self):
        self._setup_data()
        album = self.add_album_fixture()
        item = album.items()[0]
        self.run_command('embedart', '-f', self.small_artpath)
        mediafile = MediaFile(syspath(item.path))
        self.assertEqual(mediafile.images[0].data, self.image_data)

    def test_embed_art_from_album(self):
        self._setup_data()
        album = self.add_album_fixture()
        item = album.items()[0]
        album.artpath = self.small_artpath
        album.store()
        self.run_command('embedart')
        mediafile = MediaFile(syspath(item.path))
        self.assertEqual(mediafile.images[0].data, self.image_data)

    def test_embed_art_remove_art_file(self):
        self._setup_data()
        album = self.add_album_fixture()

        logging.getLogger('beets.embedart').setLevel(logging.DEBUG)

        handle, tmp_path = tempfile.mkstemp()
        os.write(handle, self.image_data)
        os.close(handle)

        album.artpath = tmp_path
        album.store()

        config['embedart']['remove_art_file'] = True
        self.run_command('embedart')

        if os.path.isfile(tmp_path):
            os.remove(tmp_path)
            self.fail(u'Artwork file {0} was not deleted'.format(tmp_path))

    def test_art_file_missing(self):
        self.add_album_fixture()
        logging.getLogger('beets.embedart').setLevel(logging.DEBUG)
        with self.assertRaises(ui.UserError):
            self.run_command('embedart', '-f', '/doesnotexist')

    def test_embed_non_image_file(self):
        album = self.add_album_fixture()
        logging.getLogger('beets.embedart').setLevel(logging.DEBUG)

        handle, tmp_path = tempfile.mkstemp()
        os.write(handle, u'I am not an image.')
        os.close(handle)

        try:
            self.run_command('embedart', '-f', tmp_path)
        finally:
            os.remove(tmp_path)

        mediafile = MediaFile(syspath(album.items()[0].path))
        self.assertFalse(mediafile.images)  # No image added.

    @require_artresizer_compare
    def test_reject_different_art(self):
        self._setup_data(self.abbey_artpath)
        album = self.add_album_fixture()
        item = album.items()[0]
        self.run_command('embedart', '-f', self.abbey_artpath)
        config['embedart']['compare_threshold'] = 20
        self.run_command('embedart', '-f', self.abbey_differentpath)
        mediafile = MediaFile(syspath(item.path))

        self.assertEqual(mediafile.images[0].data, self.image_data,
                         u'Image written is not {0}'.format(
                         self.abbey_artpath))

    @require_artresizer_compare
    def test_accept_similar_art(self):
        self._setup_data(self.abbey_similarpath)
        album = self.add_album_fixture()
        item = album.items()[0]
        self.run_command('embedart', '-f', self.abbey_artpath)
        config['embedart']['compare_threshold'] = 20
        self.run_command('embedart', '-f', self.abbey_similarpath)
        mediafile = MediaFile(syspath(item.path))

        self.assertEqual(mediafile.images[0].data, self.image_data,
                         u'Image written is not {0}'.format(
                         self.abbey_similarpath))

    def test_non_ascii_album_path(self):
        resource_path = os.path.join(_common.RSRC, 'image.mp3').encode('utf8')
        album = self.add_album_fixture()
        trackpath = album.items()[0].path
        albumpath = album.path
        shutil.copy(syspath(resource_path), syspath(trackpath))

        self.run_command('extractart', '-n', 'extracted')

        self.assertExists(syspath(os.path.join(albumpath, b'extracted.png')))


@patch('beets.art.subprocess')
@patch('beets.art.extract')
class ArtSimilarityTest(unittest.TestCase):
    def test_imagemagick_response(self, mock_extract, mock_subprocess):
        mock_extract.return_value = True
        proc = mock_subprocess.Popen.return_value
        log = logging.getLogger('beets.embedart')

        # everything is fine
        proc.returncode = 0
        proc.communicate.return_value = "10", "tagada"
        self.assertTrue(art.check_art_similarity(log, None, None, 20))
        self.assertFalse(art.check_art_similarity(log, None, None, 5))

        # small failure
        proc.returncode = 1
        proc.communicate.return_value = "tagada", "10"
        self.assertTrue(art.check_art_similarity(log, None, None, 20))
        self.assertFalse(art.check_art_similarity(log, None, None, 5))

        # bigger failure
        proc.returncode = 2
        self.assertIsNone(art.check_art_similarity(log, None, None, 20))

        # IM result parsing problems
        proc.returncode = 0
        proc.communicate.return_value = "foo", "bar"
        self.assertIsNone(art.check_art_similarity(log, None, None, 20))

        proc.returncode = 1
        self.assertIsNone(art.check_art_similarity(log, None, None, 20))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
