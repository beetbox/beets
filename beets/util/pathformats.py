from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import confuse

    PathFormat = tuple[str, str]


# Special path format key.
PF_KEY_DEFAULT = "default"
PF_KEY_QUERIES = {"comp": "comp:true", "singleton": "singleton:true"}


def get_path_formats(subview: confuse.Subview) -> list[PathFormat]:
    """Build ordered query/template pairs from layered path-format settings.

    The mapping is read through Confuse's ``items()`` view so keys from lower-
    priority sources remain visible when higher-priority config only overrides
    part of ``paths``. This keeps inherited defaults such as ``default``,
    ``comp``, and ``singleton`` available unless they are explicitly replaced.
    """
    return [(PF_KEY_QUERIES.get(q, q), v.as_str()) for q, v in subview.items()]
