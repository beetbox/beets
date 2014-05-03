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

"""Tests for the 'bucket' plugin."""

from _common import unittest
from beetsplug import bucket
from beets import config

from helper import TestHelper


class BucketPluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.plugin = bucket.BucketPlugin()

    def tearDown(self):
        self.teardown_beets()

    def _setup_config(self, bucket_year=[], bucket_alpha=[]):
        config['bucket']['bucket_year'] = bucket_year
        config['bucket']['bucket_alpha'] = bucket_alpha
        self.plugin.setup()

    def test_year_single_year(self):
        """If a single year is given, folder represents a range from this year
        to the next 'from year' of next folder."""
        self._setup_config(bucket_year=['50', '70'])

        self.assertEqual(self.plugin._tmpl_bucket('1959'), '50')
        self.assertEqual(self.plugin._tmpl_bucket('1969'), '50')

    def test_year_single_year_last_folder(self):
        """Last folder of a range extends from its year to current year."""
        self._setup_config(bucket_year=['50', '70'])
        self.assertEqual(self.plugin._tmpl_bucket('1999'), '70')

    def test_year_two_years(self):
        self._setup_config(bucket_year=['50-59', '1960-69'])
        self.assertEqual(self.plugin._tmpl_bucket('1954'), '50-59')

    def test_year_out_of_range(self):
        """If no range match, return the year"""
        self._setup_config(bucket_year=['50-59', '1960-69'])
        self.assertEqual(self.plugin._tmpl_bucket('1974'), '1974')

    def test_alpha_all_chars(self):
        self._setup_config(bucket_alpha=['ABCD', 'FGH', 'IJKL'])
        self.assertEqual(self.plugin._tmpl_bucket('garry'), 'FGH')

    def test_alpha_first_last_chars(self):
        self._setup_config(bucket_alpha=['A-D', 'F-H', 'I-Z'])
        self.assertEqual(self.plugin._tmpl_bucket('garry'), 'F-H')

    def test_alpha_out_of_range(self):
        """If no range match, return the initial"""
        self.assertEqual(self.plugin._tmpl_bucket('errol'), 'E')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
