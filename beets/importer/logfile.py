"""Helpers for writing and reading import log paths."""

from __future__ import annotations

import json

LOG_PATH_SEPARATOR = "; "


def decode_log_paths(paths: str) -> list[str]:
    """Parse an import log path list."""
    if paths.startswith("["):
        try:
            decoded_paths = json.loads(paths)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(decoded_paths, list) and all(
                isinstance(path, str) for path in decoded_paths
            ):
                return decoded_paths

    return paths.split(LOG_PATH_SEPARATOR)


def join_log_paths(paths: list[str]) -> str:
    """Join paths for import logs with JSON string escaping."""
    return json.dumps(paths, ensure_ascii=False)
