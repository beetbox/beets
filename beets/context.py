from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from beets.util import PathLike

# Holds the music dir context
_music_dir_var: ContextVar[bytes] = ContextVar("music_dir", default=b"")


def get_music_dir() -> bytes:
    """Get the current music directory context."""
    return _music_dir_var.get()


def set_music_dir(value: PathLike) -> None:
    """Set the current music directory context."""
    _music_dir_var.set(os.fsencode(value))


@contextmanager
def music_dir(value: PathLike) -> Iterator[None]:
    """Temporarily bind the active music directory for query parsing."""
    token = _music_dir_var.set(os.fsencode(value))
    try:
        yield
    finally:
        _music_dir_var.reset(token)
