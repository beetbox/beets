# This file is part of beets.
# Copyright 2021, Edgars Supe.
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

"""Tests for the 'albumtypes' plugin."""


import unittest

from beets.autotag.mb import VARIOUS_ARTISTS_ID
from beetsplug.albumtypes import AlbumTypesPlugin
from test.helper import TestHelper


class AlbumTypesPluginTest(unittest.TestCase, TestHelper):
    """Tests for albumtypes plugin."""

    def setUp(self):
        """Set up tests."""
        self.setup_beets()
        self.load_plugins('albumtypes')

    def tearDown(self):
        """Tear down tests."""
        self.unload_plugins()
        self.teardown_beets()

    def test_renames_types(self):
        """Tests if the plugin correctly renames the specified types."""
        self._set_config(
            types=[('ep', 'EP'), ('remix', 'Remix')],
            ignore_va=[],
            bracket='()'
        )
        album = self._create_album(album_types=['ep', 'remix'])
        subject = AlbumTypesPlugin()
        result = subject._atypes(album)
        self.assertEqual('(EP)(Remix)', result)
        return

    def test_returns_only_specified_types(self):
        """Tests if the plugin returns only non-blank types given in config."""
        self._set_config(
            types=[('ep', 'EP'), ('soundtrack', '')],
            ignore_va=[],
            bracket='()'
        )
        album = self._create_album(album_types=['ep', 'remix', 'soundtrack'])
        subject = AlbumTypesPlugin()
        result = subject._atypes(album)
        self.assertEqual('(EP)', result)

    def test_respects_type_order(self):
        """Tests if the types are returned in the same order as config."""
        self._set_config(
            types=[('remix', 'Remix'), ('ep', 'EP')],
            ignore_va=[],
            bracket='()'
        )
        album = self._create_album(album_types=['ep', 'remix'])
        subject = AlbumTypesPlugin()
        result = subject._atypes(album)
        self.assertEqual('(Remix)(EP)', result)
        return

    def test_ignores_va(self):
        """Tests if the specified type is ignored for VA albums."""
        self._set_config(
            types=[('ep', 'EP'), ('soundtrack', 'OST')],
            ignore_va=['ep'],
            bracket='()'
        )
        album = self._create_album(
            album_types=['ep', 'soundtrack'],
            artist_id=VARIOUS_ARTISTS_ID
        )
        subject = AlbumTypesPlugin()
        result = subject._atypes(album)
        self.assertEqual('(OST)', result)

    def test_respects_defaults(self):
        """Tests if the plugin uses the default values if config not given."""
        album = self._create_album(
            album_types=['ep', 'single', 'soundtrack', 'live', 'compilation',
                         'remix'],
            artist_id=VARIOUS_ARTISTS_ID
        )
        subject = AlbumTypesPlugin()
        result = subject._atypes(album)
        self.assertEqual('[EP][Single][OST][Live][Remix]', result)

    def _set_config(self, types: [(str, str)], ignore_va: [str], bracket: str):
        self.config['albumtypes']['types'] = types
        self.config['albumtypes']['ignore_va'] = ignore_va
        self.config['albumtypes']['bracket'] = bracket

    def _create_album(self, album_types: [str], artist_id: str = 0):
        return self.add_album(
            albumtypes='; '.join(album_types),
            mb_albumartistid=artist_id
        )
