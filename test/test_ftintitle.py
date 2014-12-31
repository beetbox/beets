# This file is part of beets.
# Copyright 2014, Fabrice Laporte.
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

"""Tests for the 'ftintitle' plugin."""

from _common import unittest
from beetsplug import ftintitle


class FtInTitlePluginTest(unittest.TestCase):
    def setUp(self):
        """Set up configuration"""
        ftintitle.FtInTitlePlugin()

    def test_split_on_feat(self):
        parts = ftintitle.split_on_feat('Alice ft. Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice feat Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice feat. Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice featuring Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice & Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice and Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice With Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice defeat Bob')
        self.assertEqual(parts, ('Alice defeat Bob', None))

    def test_contains_feat(self):
        """Test for detecting "feat." in a given title.
        """
        self.assertTrue(ftintitle.contains_feat('Lumberjack Song ft. Bob'))
        self.assertTrue(ftintitle.contains_feat('Lumberjack Song feat. Bob'))
        self.assertTrue(ftintitle.contains_feat('Lumberjack Song feat Bob'))
        self.assertTrue(ftintitle.contains_feat('Lumberjack Song featuring Bob'))
        self.assertFalse(ftintitle.contains_feat('All Things Dull & Ugly'))
        self.assertFalse(ftintitle.contains_feat('All Things Dull and Ugly'))
        self.assertFalse(ftintitle.contains_feat('Lumberjack Song With Bob'))
        self.assertFalse(ftintitle.contains_feat('Alice defeat Bob'))
        self.assertFalse(ftintitle.contains_feat('LumberjackSongft.Bob'))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
