import warnings
from importlib import import_module
from typing import Any


def deprecate_imports(
    old_module: str, new_module_by_name: dict[str, str], name: str, version: str
) -> Any:
    """Handle deprecated module imports by redirecting to new locations.

    Facilitates gradual migration of module structure by intercepting import
    attempts for relocated functionality. Issues deprecation warnings while
    transparently providing access to the moved implementation, allowing
    existing code to continue working during transition periods.
    """
    if new_module := new_module_by_name.get(name):
        warnings.warn(
            (
                f"'{old_module}.{name}' is deprecated and will be removed"
                f" in {version}. Use '{new_module}.{name}' instead."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(import_module(new_module), name)
    raise AttributeError(f"module '{old_module}' has no attribute '{name}'")
