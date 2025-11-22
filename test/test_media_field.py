import unittest

from beets.library import Item, Library


class MediaFieldTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(':memory:')
        self.lib.add_album = self.lib.add_album

    def add_album_with_items(self, items_data):
        items = []
        for data in items_data:
            item = Item(**data)
            items.append(item)
        album = self.lib.add_album(items)
        return album

    def test_album_media_field_multiple_types(self):
        items_data = [
            {"title": "Track 1", "artist": "Artist A", "media": "CD"},
            {"title": "Track 2", "artist": "Artist A", "media": "Vinyl"},
        ]
        album = self.add_album_with_items(items_data)
        media = album.media
        assert media == ["CD", "Vinyl"]

    def test_album_media_field_single_type(self):
        items_data = [
            {"title": "Track 1", "artist": "Artist A", "media": "CD"},
            {"title": "Track 2", "artist": "Artist A", "media": "CD"},
        ]
        album = self.add_album_with_items(items_data)
        media = album.media
        assert media == ["CD"]

    def test_album_with_no_media(self):
        items_data = [
            {"title": "Track 1", "artist": "Artist A"},
            {"title": "Track 2", "artist": "Artist A"},
        ]
        album = self.add_album_with_items(items_data)
        media = album.media
        assert media == []


if __name__ == "__main__":
    unittest.main()
