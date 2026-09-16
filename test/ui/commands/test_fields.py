from beets import library
from beets.test.helper import IOMixin, ItemInDBTestCase


class FieldsTest(IOMixin, ItemInDBTestCase):
    def test_fields_func(self):
        items = library.Item.all_keys()
        albums = library.Album.all_keys()

        output = set(self.run_with_output("fields").split())
        items -= output
        albums -= output

        assert len(items) == 0
        assert len(albums) == 0
