# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2020, David Swarbrick.
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


import unittest
import os
from mock import patch

from test import _common
from test.helper import TestHelper
from beets.util.artresizer import ArtResizer, pil_resize, im_resize

from beetsplug.tweet import TweetPlugin


class TweetTest(_common.TestCase, TestHelper):
    IMG_225x225 = os.path.join(_common.RSRC, b"abbey.jpg")
    IMG_225x225_SIZE = os.stat(IMG_225x225).st_size
    LOWER_MAX_FILESIZE = 5e3
    # IMG_348x348 = os.path.join(_common.RSRC, b'abbey-different.jpg')
    # IMG_500x490 = os.path.join(_common.RSRC, b'abbey-similar.jpg')

    def setUp(self):
        self.setup_beets()
        self.config["tweet"]["api_key"] = "ApIkey0"
        self.config["tweet"]["api_secret_key"] = "ApISecretkey0"
        self.config["tweet"]["access_token"] = "aCesst0ken"
        self.config["tweet"]["access_token_secret"] = "aCesst0kenSecret"
        self.load_plugins("tweet")
        # Patch import of Twitter library
        self.plugin = TweetPlugin()

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def _test_img_resize(self, resize_func):
        """Wrapper function to """
        # Check "lower maximum filesize" is truly lower than original filesize
        self.assertLess(self.LOWER_MAX_FILESIZE, self.IMG_225x225_SIZE)

        # Shrink using given method, known dimension, max quality.
        im = resize_func(
            225,
            self.IMG_225x225,
            quality=95,
            max_filesize=self.LOWER_MAX_FILESIZE,
        )

        # check valid path returned
        self.assertTrue(os.path.exists(im))
        new_file_size = os.stat(im).st_size
        # check size has decreased
        self.assertLess(new_file_size, self.IMG_225x225_SIZE)
        # check size has decreased enough
        self.assertLess(new_file_size, self.LOWER_MAX_FILESIZE)

    def test_pil_file_resize(self):
        """Test PIL resize function is lowering file size."""
        self._test_img_resize(pil_resize)

    def test_im_file_resize(self):
        """Test IM resize function is lowering file size."""
        self._test_img_resize(im_resize)

    def test_resize_not_called(self):
        """Check resize function is only called when required."""

        with patch.object(ArtResizer.shared, "resize") as mock_resize:
            a = self.add_album()
            a["artpath"] = self.IMG_225x225
            # Checking cover is less than 5MB size
            self.assertLess(self.IMG_225x225_SIZE, 5e6)
            ret = self.plugin._get_album_art_data(a)
            # Check some imagedata has been retrieved
            self.assertIsNotNone(ret)
            # Check resize wasn't called (as certainly less than 5MB)
            self.assertFalse(mock_resize.called)

    def test_status_creation(self):
        self.config["tweet"]["upload_album_art"] = False
        self.config["tweet"]["cautious"] = False
        a = self.add_album(
            **{"albumartist": "ARTIST", "album": "ALBUM", "year": 1234}
        )
        with patch.object(TweetPlugin, "_twitter_upload") as tw_upload:
            self.plugin.tweet(self.lib, [a])
            self.assertTrue(tw_upload.called)
            self.assertEqual(
                tw_upload.call_args[0], ("ARTIST - ALBUM (1234)", None)
            )


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == "__main__":
    unittest.main(defaultTest="suite")
