from dataclasses import FrozenInstanceError, asdict

import pytest

from beets.autotag import Source
from beets.library import Item
from beets.util import Likelies


def test_album_source_uses_frozen_likelies():
    items = [
        Item(
            artist="track artist",
            album="album",
            albumartist="album artist",
            year=2024,
        ),
        Item(
            artist="another artist",
            album="album",
            albumartist="album artist",
            year=2024,
        ),
    ]

    source = Source.from_items(items)

    assert isinstance(source.data, Likelies)
    assert source.data.artist == "album artist"
    assert source.data.album == "album"
    assert source.data.year == 2024
    with pytest.raises(FrozenInstanceError):
        setattr(source.data, "artist", "changed")


def test_singleton_source_constructs_fixed_metadata_fields():
    item = Item(
        artist="track artist",
        title="title",
        album="album",
        albumartist="album artist",
        mb_trackid="track id",
        mb_albumid="album id",
        data_source="MusicBrainz",
        custom_field="not source metadata",
    )

    source = Source.from_item(item)

    assert source.artist == "track artist"
    assert source.name == "title"
    assert source.id == "track id"
    assert source.data.artist == "track artist"
    assert source.data.albumartist == "album artist"
    assert source.data.mb_albumid == "album id"
    assert source.data.data_source == "MusicBrainz"
    assert not hasattr(source.data, "title")
    assert not hasattr(source.data, "custom_field")


def test_likelies_converts_to_detached_dictionary():
    source = Source.from_item(Item(artist="artist", title="title"))

    metadata = asdict(source.data)
    metadata["artist"] = "changed"

    assert isinstance(metadata, dict)
    assert metadata["album"] == ""
    assert source.data.artist == "artist"
