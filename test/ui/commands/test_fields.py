from beets import library
from beets.test.helper import IOMixin, ItemInDBTestCase
from beets.ui.commands.fields import fields_func


class FieldsTest(IOMixin, ItemInDBTestCase):
    def remove_keys(self, keys, text):
        for i in text:
            try:
                keys.remove(i)
            except ValueError:
                pass

    def add_item_with_flex_attr(self, attr_name, attr_value):
        """Helper to add an item with a flexible attribute."""
        item = self.add_item_fixture()
        setattr(item, attr_name, attr_value)
        item.store()
        return item

    def test_fields_func(self):
        fields_func(self.lib, [], [])
        items = library.Item.all_keys()
        albums = library.Album.all_keys()

        output = self.io.stdout.get().split()
        self.remove_keys(items, output)
        self.remove_keys(albums, output)

        assert len(items) == 0
        assert len(albums) == 0

    def test_fields_func_with_flex_attrs(self):
        """Test that flexible attributes are displayed."""
        # Add items with flexible attributes
        self.add_item_with_flex_attr("custom_field", "value1")
        self.add_item_with_flex_attr("another_custom", "value2")

        # Add album with flexible attribute
        album = self.add_album_fixture()
        album.custom_album_field = "album_value"
        album.store()

        fields_func(self.lib, [], [])

        output = self.io.stdout.get()

        # Verify flexible attributes are listed
        assert "Item flexible attributes:" in output
        assert "custom_field" in output
        assert "another_custom" in output
        assert "Album flexible attributes:" in output
        assert "custom_album_field" in output
