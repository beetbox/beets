# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2015, Nikhil Gupta.
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

"""Tests for the 'betterlisting' plugin."""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from test._common import unittest
from beetsplug import betterlisting

from test.helper import TestHelper


class BetterListingPluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.load_plugins('betterlisting')
        self.plugin = betterlisting.BetterListingPlugin()
        default_config = {key: val.get() for key, val in
                          self.plugin.config.items()}
        self._setup_config(**default_config)

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def _setup_config(self, **values):
        for key, val in values.iteritems():
            self.plugin.config[key] = val


class TemplateFunctionsForStringPaddingTest(BetterListingPluginTest):

    def test_template_function_for_right_padding(self):
        """If a string and width is given, right pads that string correctly."""
        self.assertEqual(self.plugin.tmpl_rpad(u'text', "9"), u'text     ')
        self.assertEqual(self.plugin.tmpl_rpad(u'text', "0"), u'text')
        self.assertEqual(self.plugin.tmpl_rpad(u'text▃ ', "9"), u'text▃    ')
        self.assertEqual(self.plugin.tmpl_rpad(u'textⓂ️ ', "9"), u'textⓂ️   ')

    def test_template_function_for_left_padding(self):
        """If a string and width is given, left pads that string correctly."""
        self.assertEqual(self.plugin.tmpl_lpad(u'text', "9"), u'     text')
        self.assertEqual(self.plugin.tmpl_lpad(u'text', "0"), u'text')
        self.assertEqual(self.plugin.tmpl_lpad(u'text▃ ', "9"), u'   text▃ ')
        self.assertEqual(self.plugin.tmpl_lpad(u'textⓂ️ ', "9"), u'  textⓂ️ ')

    def test_template_function_for_right_padding_with_trimming(self):
        """If a string and width is given, right pads that string while trimming
        it to the specified width."""
        self.assertEqual(self.plugin.tmpl_rtrimpad(u'text', "9"), u'text     ')
        self.assertEqual(self.plugin.tmpl_rtrimpad(u'text', "3"), u'tex')
        self.assertEqual(self.plugin.tmpl_rtrimpad(u'text', "0"), u'')
        self.assertEqual(self.plugin.tmpl_rtrimpad(u'text', "-2"), u'')
        self.assertEqual(self.plugin.tmpl_rtrimpad(u'text▃ ', "5"), u'text▃')
        self.assertEqual(self.plugin.tmpl_rtrimpad(u'textⓂ️ ', "5"), u'textⓂ')

    def test_template_function_for_left_padding_with_trimming(self):
        """If a string and width is given, left pads that string while trimming
        it to the specified width."""
        self.assertEqual(self.plugin.tmpl_ltrimpad(u'text', "9"), u'     text')
        self.assertEqual(self.plugin.tmpl_ltrimpad(u'text', "3"), u'ext')
        self.assertEqual(self.plugin.tmpl_ltrimpad(u'text', "0"), u'')
        self.assertEqual(self.plugin.tmpl_ltrimpad(u'text', "-2"), u'')
        self.assertEqual(self.plugin.tmpl_ltrimpad(u'text▃ ', "5"), u'ext▃ ')
        self.assertEqual(self.plugin.tmpl_ltrimpad(u'textⓂ️ ', "5"), u'xtⓂ️ ')


class TemplateFunctionsForColoredStringTest(BetterListingPluginTest):

    def test_template_function_for_coloring_strings(self):
        """If a string and color is given, colorize string with that color"""
        self.assertEqual(self.plugin.tmpl_colorize(u'a'), u'a')
        self.assertEqual(self.plugin.tmpl_colorize(u'a', u'  '), u'a')

        expected = u'\x1b[37;01ma\x1b[39;49;00m'
        self.assertEqual(self.plugin.tmpl_colorize(u'a', u'white'), expected)
        self.assertEqual(self.plugin.tmpl_colorize(u'a', u' white  '), expected)

        expected = u'\x1b[35ma\x1b[39;49;00m'
        self.assertEqual(self.plugin.tmpl_colorize(u'a', u'purple'), expected)


class TemplateFunctionsForSparkBarsTest(BetterListingPluginTest):

    def test_template_function_for_spark_bar(self):
        """If a count and total is given, produce a spark bar for that ratio"""
        self.assertEqual(self.plugin.tmpl_sparkbar(9, 80), u' ')
        self.assertEqual(self.plugin.tmpl_sparkbar(10, 80), u'\u2581')
        self.assertEqual(self.plugin.tmpl_sparkbar(8, 8), u'\u2587')

    def test_template_function_for_colored_spark_bar(self):
        """If count, total and color is given, produce a colored spark bar"""
        expected = u'\x1b[35m\u2583\x1b[39;49;00m'
        self.assertEqual(self.plugin.tmpl_sparkbar(4, 10, u'purple'), expected)

    def test_template_function_for_used_configured_spark_bar(self):
        """If user has specified spark bars, produce spark bar from them"""
        self._setup_config(sparks=u'▆▄▂ ')
        self.assertEqual(self.plugin.tmpl_sparkbar(4, 20), u' ')
        self.assertEqual(self.plugin.tmpl_sparkbar(15, 20), u'\u2586')
        self.assertEqual(self.plugin.tmpl_sparkbar(23, 18), u'\u2586')


class TemplateFieldsForDurationTest(BetterListingPluginTest):

    def setUp(self):
        super(self.__class__, self).setUp()

    def add_fixtures(self, *lengths):
        """Add fixtures for the current tests."""
        items = []

        for length in lengths:
            if length:
                items.append(self.add_item(path="/", length=length))
            else:
                items.append(self.add_item(path="/"))

        return [self.lib.add_album(items), items]

    def test_template_fields_for_duration(self):
        """Duration fields should return time in human readable format"""
        album, items = self.add_fixtures(0, 210, 430, 9000)
        self.assertEqual(self.plugin.field_duration(items[0]), "00:00")
        self.assertEqual(self.plugin.field_duration(items[1]), "03:30")
        self.assertEqual(self.plugin.field_duration(items[2]), "07:10")
        self.assertEqual(self.plugin.field_duration(items[3]), "150:00")
        self.assertEqual(self.plugin.field_duration(album), "160:40")
        self.assertEqual(self.plugin.album_field_avg_duration(album), "40:10")

        album, _ = self.add_fixtures(5998, 5999, 6000, 6001, 6002)
        self.assertEqual(self.plugin.field_duration(album), "500:00")
        self.assertEqual(self.plugin.album_field_avg_duration(album), "100:00")

    def test_template_fields_for_duration_with_custom_format(self):
        """Time format for duration fields should be configurable by the user"""
        album, items = self.add_fixtures(0, 210, 300, 10000)

        self._setup_config(duration_format=u'{mins:04d}m')
        self.assertEqual(self.plugin.field_duration(album), "0175m")
        self.assertEqual(self.plugin.album_field_avg_duration(album), "0043m")

        self._setup_config(duration_format=u'{mins:2d}m{secs:03d}s')
        self.assertEqual(self.plugin.field_duration(album), "175m010s")
        self.assertEqual(self.plugin.album_field_avg_duration(album), "43m047s")

    def test_template_fields_for_duration_usable_in_sorting(self):
        """For sorting, duration sort fields should return integer values"""
        album, items = self.add_fixtures(0, 100, 505)
        self.assertEqual(self.plugin.field_duration_sort(items[0]), 0)
        self.assertEqual(self.plugin.field_duration_sort(items[1]), 100)
        self.assertEqual(self.plugin.field_duration_sort(album), 605)
        self.assertEqual(self.plugin.album_field_avg_duration_sort(album), 201)

        album, _ = self.add_fixtures(None, 5998, 5999, 6000, 6001, 6002)
        self.assertEqual(self.plugin.album_field_avg_duration_sort(album), 5000)

    def test_template_field_for_duration_based_spark_bar(self):
        """For listing purpose, duration bar fields should return spark bar"""
        album, items = self.add_fixtures(20, 80, 91, 340, 720)
        self.assertEqual(self.plugin.field_duration_bar(items[0]), u' ')
        self.assertEqual(self.plugin.field_duration_bar(items[1]), u'\u2581')
        self.assertEqual(self.plugin.field_duration_bar(items[2]), u'\u2582')
        self.assertEqual(self.plugin.field_duration_bar(items[3]), u'\u2587')
        self.assertEqual(self.plugin.field_duration_bar(items[4]), u'\u2587')
        self.assertEqual(self.plugin.field_duration_bar(album), u'\u2585')

    def test_template_field_for_duration_based_custom_spark_bar(self):
        """Spark bar for duration fields should be configurable by the user"""
        album, _ = self.add_fixtures(20, 80, 91, 340, 720)
        self._setup_config(track_length=800)
        self.assertEqual(self.plugin.field_duration_bar(album), u'\u2582')
        self._setup_config(track_length=600, sparks=u'▆▄▂')
        self.assertEqual(self.plugin.field_duration_bar(album), u'\u2584')
        self._setup_config(sparks=u'')
        self.assertEqual(self.plugin.field_duration_bar(album), u'')


class BetterListingPluginLyricsFieldsTest(BetterListingPluginTest):
    def add_fixtures(self, lyrics=3, total=3):
        """Add fixtures for the current tests."""
        items = []
        for i in range(total):
            text = None if i + 1 > lyrics else "Some lyrics"
            items.append(self.add_item(path="/", lyrics=text))
        return [self.lib.add_album(items), items]

    def test_template_field_for_lyrics_sort(self):
        """For sorting queries, lyrics_sort field should return float value"""
        album, items = self.add_fixtures(lyrics=3, total=5)
        self.assertEqual(self.plugin.field_lyrics_sort(items[0]), 1)
        self.assertEqual(self.plugin.field_lyrics_sort(items[4]), 0)
        self.assertEqual(self.plugin.field_lyrics_sort(album), 0.6)
        album, _ = self.add_fixtures(lyrics=3, total=3)
        self.assertEqual(self.plugin.field_lyrics_sort(album), 1)
        album, _ = self.add_fixtures(lyrics=0, total=3)
        self.assertEqual(self.plugin.field_lyrics_sort(album), 0)

    def test_template_field_for_lyrics_icon(self):
        """For listing, lyrics_icon should return corresponding icon"""
        album, items = self.add_fixtures(lyrics=3, total=5)
        self.assertEqual(self.plugin.field_lyrics_icon(items[0]), u'\U0001f4d7')
        self.assertEqual(self.plugin.field_lyrics_icon(items[4]), u'\U0001f4d5')
        self.assertEqual(self.plugin.field_lyrics_icon(album), u'\U0001f4d9')
        album, _ = self.add_fixtures(lyrics=3, total=3)
        self.assertEqual(self.plugin.field_lyrics_icon(album), u'\U0001f4d7')
        album, _ = self.add_fixtures(lyrics=0, total=3)
        self.assertEqual(self.plugin.field_lyrics_icon(album), u'\U0001f4d5')

    def test_template_field_for_lyrics_icon_with_custom_format_strings(self):
        """lyrics_icon field should be configurable by the user"""
        album, items = self.add_fixtures(lyrics=3, total=5)
        self._setup_config(icon_lyrics_all=u'%colorize{◎ , green}',
                           icon_lyrics_none=u'%colorize{◎ , red}',
                           icon_lyrics_some=u'%colorize{◎ , yellow}')
        expected = u'\x1b[32;01m\u25ce \x1b[39;49;00m'
        self.assertEqual(self.plugin.field_lyrics_icon(items[0]), expected)
        expected = u'\x1b[31;01m\u25ce \x1b[39;49;00m'
        self.assertEqual(self.plugin.field_lyrics_icon(items[4]), expected)
        expected = u'\x1b[33;01m\u25ce \x1b[39;49;00m'
        self.assertEqual(self.plugin.field_lyrics_icon(album), expected)
        album, _ = self.add_fixtures(lyrics=3, total=3)
        expected = u'\x1b[32;01m\u25ce \x1b[39;49;00m'
        self.assertEqual(self.plugin.field_lyrics_icon(album), expected)
        album, _ = self.add_fixtures(lyrics=0, total=3)
        expected = u'\x1b[31;01m\u25ce \x1b[39;49;00m'
        self.assertEqual(self.plugin.field_lyrics_icon(album), expected)

    def test_template_field_for_lyrics_icon_with_unicode_special_chars(self):
        """lyrics_icon field should be configurable by the user"""
        album, items = self.add_fixtures(lyrics=3, total=5)
        self._setup_config(icon_lyrics_all=127477, icon_lyrics_none=127462,
                           icon_lyrics_some=127474)
        self.assertEqual(self.plugin.field_lyrics_icon(items[0]), u'\U0001f1f5')
        self.assertEqual(self.plugin.field_lyrics_icon(items[4]), u'\U0001f1e6')
        self.assertEqual(self.plugin.field_lyrics_icon(album), u'\U0001f1f2')
        album, _ = self.add_fixtures(lyrics=3, total=3)
        self.assertEqual(self.plugin.field_lyrics_icon(album), u'\U0001f1f5')
        album, _ = self.add_fixtures(lyrics=0, total=3)
        self.assertEqual(self.plugin.field_lyrics_icon(album), u'\U0001f1e6')


class BetterListingPluginFieldsForAlbumTotalTest(BetterListingPluginTest):
    def add_fixtures(self, available=3, total=5):
        """Add fixtures for the current tests."""
        items = []
        for _ in range(available):
            items.append(self.add_item(path="/", tracktotal=total))
        return self.lib.add_album(items)

    def test_album_fields_when_some_tracks_missing(self):
        """Fields should return correct values when some tracks are missing"""
        album = self.add_fixtures(available=4, total=10)
        self.assertEqual(self.plugin.album_field_available(album), 4)
        self.assertEqual(self.plugin.album_field_missing(album), 6)
        self.assertEqual(self.plugin.album_field_total(album), 10)

    def test_album_fields_when_all_tracks_present(self):
        """Fields should return correct values when no track is missing"""
        album = self.add_fixtures(available=10, total=10)
        self.assertEqual(self.plugin.album_field_missing_icon(album), u'')
        self.assertEqual(self.plugin.album_field_missing_bar(album), u' ')
        self.assertEqual(self.plugin.album_field_available_bar(album),
                         u'\u2587')

    def test_album_fields_for_missing_icon(self):
        """missing_icon field should return corresponding icon"""
        album = self.add_fixtures(available=4, total=10)
        expected = u'\x1b[31;01m\u25ce\x1b[39;49;00m'
        self.assertEqual(self.plugin.album_field_missing_icon(album), expected)

        album = self.add_fixtures(available=10, total=10)
        self.assertEqual(self.plugin.album_field_missing_icon(album), u'')

    def test_album_fields_for_missing_icon_with_custom_config_format(self):
        """missing_icon field should be configurable by the user"""
        self._setup_config(icon_missing_some=u'%colorize{ɱ,red}',
                           icon_missing_none=u'%colorize{ɱ,green}')
        album = self.add_fixtures(available=4, total=10)
        expected = u'\x1b[31;01m\u0271\x1b[39;49;00m'
        self.assertEqual(self.plugin.album_field_missing_icon(album), expected)

        expected = u'\x1b[32;01m\u0271\x1b[39;49;00m'
        album = self.add_fixtures(available=10, total=10)
        self.assertEqual(self.plugin.album_field_missing_icon(album), expected)

    def test_album_fields_for_missing_icon_with_unicode_special_chars(self):
        """missing_icon field should be configurable by the user"""
        self._setup_config(icon_missing_some=127477, icon_missing_none=127474)
        album = self.add_fixtures(available=4, total=10)
        self.assertEqual(self.plugin.album_field_missing_icon(album),
                         u'\U0001f1f5')

        album = self.add_fixtures(available=10, total=10)
        self.assertEqual(self.plugin.album_field_missing_icon(album),
                         u'\U0001f1f2')

    def test_album_fields_for_missing_bar(self):
        """missing_bar should return a spark bar for number of tracks missing"""
        album = self.add_fixtures(available=5, total=8)
        self.assertEqual(self.plugin.album_field_missing_bar(album), u'\u2583')

        album = self.add_fixtures(available=8, total=8)
        self.assertEqual(self.plugin.album_field_missing_bar(album), u' ')

    def test_album_fields_for_available_bar(self):
        """available_bar should return a spark bar for number of tracks
        present"""
        album = self.add_fixtures(available=2, total=8)
        self.assertEqual(self.plugin.album_field_available_bar(album),
                         u'\u2582')

        album = self.add_fixtures(available=8, total=8)
        self.assertEqual(self.plugin.album_field_available_bar(album),
                         u'\u2587')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
