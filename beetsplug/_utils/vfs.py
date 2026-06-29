"""A simple utility for constructing filesystem-like trees from beets
libraries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from beets import util

if TYPE_CHECKING:
    from beets.library import Library


class Node(NamedTuple):
    files: dict[str, int]
    # Maps filenames to Item ids.

    dirs: dict[str, Node]
    # Maps directory names to child nodes.


def _insert(node: Node, path: list[str], itemid: int):
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
        dest = item.destination(relative_to_libdir=True)
        parts = util.components(util.as_string(dest))
        _insert(root, parts, item.id)
    return root
