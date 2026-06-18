from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, NamedTuple

from beets.util import AttrDict, get_most_common_tags

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.library import Item


class Source(NamedTuple):
    type: Literal["album", "track"]
    artist: str
    name: str
    data: AttrDict[Any]
    items: Sequence[Item]
    id: str
    id_consensus: bool

    @property
    def desc(self) -> str:
        return f"{self.artist} - {self.name}"

    @property
    def va_likely(self) -> bool:
        return len({i.artist for i in self.items}) > 1 or any(
            i.comp for i in self.items
        )

    @classmethod
    def from_items(cls, items: Sequence[Item]) -> Source:
        """Create a Source object from a list of items."""
        likelies = get_most_common_tags(items)
        return cls(
            type="album",
            artist=likelies["artist"],
            name=likelies["album"],
            data=AttrDict(likelies),
            items=items,
            id=likelies["mb_albumid"],
            id_consensus=len({i.mb_albumid for i in items}) == 1,
        )

    @classmethod
    def from_item(cls, item: Item) -> Source:
        """Create a Source object from an item."""
        return cls(
            type="track",
            artist=item.artist,
            name=item.title,
            data=AttrDict(item),
            items=[item],
            id=item.mb_trackid,
            id_consensus=True,
        )
