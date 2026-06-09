from beets import library
from beets.test.helper import IOMixin, ItemInDBTestCase
from beets.ui.commands.fields import fields_func


class FieldsTest(IOMixin, ItemInDBTestCase):
    def test_fields_func(self):
        fields_func(self.lib, [], [])
        items = library.Item.all_keys()
        albums = library.Album.all_keys()

        output = set(self.io.getoutput().split())
        items -= output
        albums -= output

        assert len(items) == 0
        assert len(albums) == 0
