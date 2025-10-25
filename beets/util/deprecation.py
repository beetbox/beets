from __future__ import annotations

import warnings
from importlib import import_module
from typing import Any

from packaging.version import Version

import beets


def _format_message(old: str, new: str | None = None) -> str:
    next_major = f"{Version(beets.__version__).major + 1}.0.0"
    msg = f"{old} is deprecated and will be removed in version {next_major}."
    if new:
        msg += f" Use {new} instead."

    return msg


def deprecate_for_maintainers(
    old: str, new: str | None = None, stacklevel: int = 1
) -> None:
    """Issue a deprecation warning visible to maintainers during development.

    Emits a DeprecationWarning that alerts developers about deprecated code
    patterns. Unlike user-facing warnings, these are primarily for internal
    code maintenance and appear during test runs or with warnings enabled.
    """
    warnings.warn(
        _format_message(old, new), DeprecationWarning, stacklevel=stacklevel + 1
    )


def deprecate_imports(
    old_module: str, new_module_by_name: dict[str, str], name: str
) -> Any:
    """Handle deprecated module imports by redirecting to new locations.

    Facilitates gradual migration of module structure by intercepting import
    attempts for relocated functionality. Issues deprecation warnings while
    transparently providing access to the moved implementation, allowing
    existing code to continue working during transition periods.
    """
    if new_module := new_module_by_name.get(name):
        deprecate_for_maintainers(
            f"'{old_module}.{name}'", f"'{new_module}.{name}'", stacklevel=2
        )

        return getattr(import_module(new_module), name)
    raise AttributeError(f"module '{old_module}' has no attribute '{name}'")
