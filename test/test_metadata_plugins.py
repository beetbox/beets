# This file is part of beets.
# Copyright 2025, beetbox.
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

"""Tests for metadata source plugin interface."""

import pytest

from beets import config, metadata_plugins
from beets.autotag import AlbumInfo, TrackInfo
from beets.library import Item
from beets.metadata_plugins import MetadataSourcePlugin, _get_distance
from beets.test.helper import BeetsTestCase


class TestMetadataSourceDistance(BeetsTestCase):
    """Test the _get_distance function for metadata source plugins."""

    def setUp(self):
        super().setUp()
        # Set up config with a source weight
        config["match"]["distance_weights"]["source"] = 0.5

    def test_matching_source_has_no_penalty(self):
        """Test that matching data source does not add penalty."""
        # Create an AlbumInfo with a specific data source
        album_info = AlbumInfo(
            album="Test Album",
            album_id="test-id",
            artist="Test Artist",
            tracks=[],
        )
        album_info.data_source = "MusicBrainz"

        # Create a config view for the plugin
        plugin_config = config["musicbrainz"]
        plugin_config["source_weight"] = 0.5

        # Calculate distance when sources match
        dist = _get_distance(plugin_config, "MusicBrainz", album_info)

        # Should have no penalty when sources match
        assert dist.distance == 0.0

    def test_different_source_has_penalty(self):
        """Test that different data source adds penalty."""
        # Create an AlbumInfo with a specific data source
        album_info = AlbumInfo(
            album="Test Album",
            album_id="test-id",
            artist="Test Artist",
            tracks=[],
        )
        album_info.data_source = "Discogs"

        # Create a config view for the plugin
        plugin_config = config["musicbrainz"]
        plugin_config["source_weight"] = 0.5

        # Calculate distance when sources don't match
        dist = _get_distance(plugin_config, "MusicBrainz", album_info)

        # Should have a penalty when sources don't match
        assert dist.distance > 0.0
        assert dist["source"] > 0.0

    def test_track_matching_source_has_no_penalty(self):
        """Test that matching data source does not add penalty for tracks."""
        # Create a TrackInfo with a specific data source
        track_info = TrackInfo(
            title="Test Track",
            track_id="test-track-id",
        )
        track_info.data_source = "MusicBrainz"

        # Create a config view for the plugin
        plugin_config = config["musicbrainz"]
        plugin_config["source_weight"] = 0.5

        # Calculate distance when sources match
        dist = _get_distance(plugin_config, "MusicBrainz", track_info)

        # Should have no penalty when sources match
        assert dist.distance == 0.0

    def test_track_different_source_has_penalty(self):
        """Test that different data source adds penalty for tracks."""
        # Create a TrackInfo with a specific data source
        track_info = TrackInfo(
            title="Test Track",
            track_id="test-track-id",
        )
        track_info.data_source = "Discogs"

        # Create a config view for the plugin
        plugin_config = config["musicbrainz"]
        plugin_config["source_weight"] = 0.5

        # Calculate distance when sources don't match
        dist = _get_distance(plugin_config, "MusicBrainz", track_info)

        # Should have a penalty when sources don't match
        assert dist.distance > 0.0
        assert dist["source"] > 0.0


class TestMultipleMetadataSourcePlugins(BeetsTestCase):
    """Test behavior with multiple metadata source plugins loaded."""

    def setUp(self):
        super().setUp()
        config["match"]["distance_weights"]["source"] = 0.5
        
    def test_album_distance_single_matching_plugin(self):
        """Test that a single matching plugin adds no penalty."""
        # Create items and album info
        items = [
            Item(
                title="Track 1",
                track=1,
                artist="Test Artist",
                album="Test Album",
                length=180,
            )
        ]
        
        album_info = AlbumInfo(
            album="Test Album",
            album_id="test-id",
            artist="Test Artist",
            tracks=[
                TrackInfo(
                    title="Track 1",
                    track_id="track-1",
                    index=1,
                    length=180,
                )
            ],
        )
        album_info.data_source = "MusicBrainz"
        album_info.tracks[0].data_source = "MusicBrainz"
        
        # Calculate album distance using the metadata_plugins module
        # This simulates a MusicBrainz plugin calculating distance
        plugin_config = config["musicbrainz"]
        plugin_config["source_weight"] = 0.5
        
        mapping = {items[0]: album_info.tracks[0]}
        
        # When the album is from MusicBrainz and we're using the MusicBrainz plugin
        dist = _get_distance(plugin_config, "MusicBrainz", album_info)
        
        # The distance should be 0 (no source penalty)
        assert dist.distance == 0.0
        
    def test_album_distance_single_non_matching_plugin(self):
        """Test that a single non-matching plugin adds penalty."""
        # Create items and album info
        items = [
            Item(
                title="Track 1",
                track=1,
                artist="Test Artist",
                album="Test Album",
                length=180,
            )
        ]
        
        album_info = AlbumInfo(
            album="Test Album",
            album_id="test-id",
            artist="Test Artist",
            tracks=[
                TrackInfo(
                    title="Track 1",
                    track_id="track-1",
                    index=1,
                    length=180,
                )
            ],
        )
        album_info.data_source = "Discogs"
        album_info.tracks[0].data_source = "Discogs"
        
        # Calculate album distance using the metadata_plugins module
        # This simulates a MusicBrainz plugin calculating distance for a Discogs album
        plugin_config = config["musicbrainz"]
        plugin_config["source_weight"] = 0.5
        
        mapping = {items[0]: album_info.tracks[0]}
        
        # When the album is from Discogs but we're using the MusicBrainz plugin
        dist = _get_distance(plugin_config, "MusicBrainz", album_info)
        
        # The distance should be > 0 (source penalty applied)
        assert dist.distance > 0.0
        assert dist["source"] > 0.0
