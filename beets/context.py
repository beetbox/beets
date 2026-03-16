from contextvars import ContextVar

# Holds the music dir context
_music_dir_var: ContextVar[bytes] = ContextVar("music_dir", default=b"")


def get_music_dir() -> bytes:
    """Get the current music directory context."""
    return _music_dir_var.get()


def set_music_dir(value: bytes) -> None:
    """Set the current music directory context."""
    _music_dir_var.set(value)
