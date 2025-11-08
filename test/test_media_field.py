from beets.library import Item
from beets import library

def test_album_media_field(tmp_path):
    lib = library.Library(path=str(tmp_path / "library.db"),
                          directory=str(tmp_path / "music"))

    item = Item(title="Test Song", album="Test Album", media="Vinyl")
    album = lib.add_album([item])   

    assert album.media == "Vinyl"