"""A simple utility for constructing filesystem-like trees from beets
libraries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from beets import util

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.library import Item, Library


class Node(NamedTuple):
    files: dict[str, int]
    # Maps filenames to Item ids.

    dirs: dict[str, Node]
    # Maps directory names to child nodes.


def item_components(item: Item) -> list[str]:
    """Return an item's path components relative to the library directory."""
    return util.components(
        util.as_string(item.destination(relative_to_libdir=True))
    )


def item_path(item: Item) -> str:
    """Return an item's location in the tree as a "/"-separated path.

    ``Item.destination`` uses the platform's path separator, whereas the tree -
    and the clients addressing files in it - always use "/".
    """
    return "/".join(item_components(item))


def _insert(node: Node, path: Sequence[str], itemid: int) -> None:
    """Insert an item into a virtual filesystem node."""
    if len(path) == 1:
        # Last component. Insert file.
        node.files[path[0]] = itemid
    else:
        # In a directory.
        dirname = path[0]
        rest = path[1:]
        if dirname not in node.dirs:
            node.dirs[dirname] = Node({}, {})
        _insert(node.dirs[dirname], rest, itemid)


def libtree(lib: Library) -> Node:
    """Generates a filesystem-like directory tree for the files
    contained in `lib`. Filesystem nodes are (files, dirs) named
    tuples in which both components are dictionaries. The first
    maps filenames to Item ids. The second maps directory names to
    child node tuples.
    """
    root = Node({}, {})
    for item in lib.items():
        if item.id is None:
            continue
        _insert(root, item_components(item), item.id)
    return root
