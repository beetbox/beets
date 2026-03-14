"""Tests for the 'deezer' plugin"""

from mediafile import MediaFile

from beets.library import Item
from beets.test.helper import PluginTestCase
from beets.util import syspath


class DeezerMediaFieldTest(PluginTestCase):
    """Test that Deezer IDs are written to and read from media files."""

    plugin = "deezer"

    def test_deezer_track_id_written_to_file(self):
        """Verify deezer_track_id is written to media files."""
        item = self.add_item_fixture()
        item.deezer_track_id = 123456789
        item.write()

        # Read back from file (media files store as strings)
        mf = MediaFile(syspath(item.path))
        assert mf.deezer_track_id == "123456789"

    def test_deezer_album_id_written_to_file(self):
        """Verify deezer_album_id is written to media files."""
        item = self.add_item_fixture()
        item.deezer_album_id = 987654321
        item.write()

        # Read back from file (media files store as strings)
        mf = MediaFile(syspath(item.path))
        assert mf.deezer_album_id == "987654321"

    def test_deezer_artist_id_written_to_file(self):
        """Verify deezer_artist_id is written to media files."""
        item = self.add_item_fixture()
        item.deezer_artist_id = 111222333
        item.write()

        # Read back from file (media files store as strings)
        mf = MediaFile(syspath(item.path))
        assert mf.deezer_artist_id == "111222333"

    def test_deezer_ids_read_from_file(self):
        """Verify Deezer IDs can be read from file into Item."""
        item = self.add_item_fixture()
        mf = MediaFile(syspath(item.path))
        mf.deezer_track_id = "123456"
        mf.deezer_album_id = "654321"
        mf.deezer_artist_id = "999888"
        mf.save()

        # Read back into Item (beets converts to int from item_types)
        item_reloaded = Item.from_path(item.path)
        assert item_reloaded.deezer_track_id == 123456
        assert item_reloaded.deezer_album_id == 654321
        assert item_reloaded.deezer_artist_id == 999888

    def test_deezer_ids_persist_across_writes(self):
        """Verify IDs are not lost when updating other fields."""
        item = self.add_item_fixture()
        item.deezer_track_id = 123456
        item.deezer_album_id = 654321
        item.write()

        # Update different field
        item.title = "New Title"
        item.write()

        # Verify IDs still in file (media files store as strings)
        mf = MediaFile(syspath(item.path))
        assert mf.deezer_track_id == "123456"
        assert mf.deezer_album_id == "654321"

    def test_deezer_ids_not_in_musicbrainz_fields(self):
        """Verify Deezer IDs don't pollute MusicBrainz fields."""
        item = self.add_item_fixture()
        # Set Deezer IDs
        item.deezer_track_id = 123456789
        item.deezer_album_id = 987654321
        item.deezer_artist_id = 111222333
        item.write()

        # Read back and verify MusicBrainz fields are NOT set to Deezer IDs
        mf = MediaFile(syspath(item.path))

        # MusicBrainz fields should be None or empty, not Deezer IDs
        assert mf.mb_trackid != "123456789"
        assert mf.mb_albumid != "987654321"
        assert mf.mb_artistid != "111222333"
        assert mf.mb_albumartistid != "111222333"

        # Deezer IDs should be in their own fields
        assert mf.deezer_track_id == "123456789"
        assert mf.deezer_album_id == "987654321"
        assert mf.deezer_artist_id == "111222333"
