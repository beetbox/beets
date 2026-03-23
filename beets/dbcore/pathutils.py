from __future__ import annotations

import os
from typing import TypeVar

from beets import context, util

MaybeBytes = TypeVar("MaybeBytes", bytes, None)


def normalize_path_for_db(path: MaybeBytes) -> MaybeBytes:
    """Convert an absolute library path to its database representation."""
    if not path or not os.path.isabs(path):
        return path

    music_dir = context.get_music_dir()
    if not music_dir:
        return path

    if path == music_dir:
        return os.path.relpath(path, music_dir)

    if path.startswith(os.path.join(music_dir, b"")):
        return os.path.relpath(path, music_dir)

    return path


def expand_path_from_db(path: bytes) -> bytes:
    """Convert a stored database path to an absolute library path."""
    music_dir = context.get_music_dir()
    if path and not os.path.isabs(path) and music_dir:
        return util.normpath(os.path.join(music_dir, path))

    return path
