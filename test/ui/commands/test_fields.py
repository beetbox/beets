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

    def test_fields_func(self):
        fields_func(self.lib, [], [])
        items = library.Item.all_keys()
        albums = library.Album.all_keys()

        output = self.io.stdout.get().split()
        self.remove_keys(items, output)
        self.remove_keys(albums, output)

        assert len(items) == 0
        assert len(albums) == 0
