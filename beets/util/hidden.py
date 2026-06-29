"""Simple library to work out if a file is hidden on different platforms."""

import ctypes
import os
import stat
import sys
from pathlib import Path


def is_hidden(path: bytes | Path) -> bool:
    """
    Determine whether the given path is treated as a 'hidden file' by the OS.
    """

    if isinstance(path, bytes):
        path = Path(os.fsdecode(path))

    # TODO: Avoid doing a platform check on every invocation of the function.
    # TODO: Stop supporting 'bytes' inputs once 'pathlib' is fully integrated.

    if sys.platform == "win32":
        # On Windows, we check for an FS-provided attribute.

        # FILE_ATTRIBUTE_HIDDEN = 2 (0x2) from GetFileAttributes documentation.
        hidden_mask = 2

        # Retrieve the attributes for the file.
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))

        # Ensure the attribute mask is valid.
        if attrs < 0:
            return False

        # Check for the hidden attribute.
        return attrs & hidden_mask

    # On OS X, we check for an FS-provided attribute.
    if sys.platform == "darwin":
        if hasattr(os.stat_result, "st_flags") and hasattr(stat, "UF_HIDDEN"):
            if path.lstat().st_flags & stat.UF_HIDDEN:
                return True

    # On all non-Windows platforms, we check for a '.'-prefixed file name.
    if path.name.startswith("."):
        return True

    return False
