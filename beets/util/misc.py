from __future__ import annotations

from typing import TYPE_CHECKING

from beets.util.io import plurality

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from beets.library.models import Item


def get_most_common_tags(
    items: Sequence[Item],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Extract the likely current metadata for an album given a list of its
    items. Return two dictionaries:
     - The most common value for each field.
     - Whether each field's value was unanimous (values are booleans).
    """
    assert items  # Must be nonempty.

    likelies: dict[str, int | str | Any] = {}
    consensus: dict[str, bool] = {}
    fields: list[str] = [
        "artist",
        "album",
        "albumartist",
        "year",
        "disctotal",
        "mb_albumid",
        "label",
        "barcode",
        "catalognum",
        "country",
        "media",
        "albumdisambig",
        "data_source",
    ]
    field: str
    for field in fields:
        values: list[int | str | Any] = [
            item.get(field) for item in items if item
        ]
        freq: int
        likelies[field], freq = plurality(values)
        consensus[field] = freq == len(values)

    # If there's an album artist consensus, use this for the artist.
    if consensus["albumartist"] and likelies["albumartist"]:
        likelies["artist"] = likelies["albumartist"]

    return likelies, consensus
