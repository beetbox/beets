from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from .color import colorize

if TYPE_CHECKING:
    from beets.dbcore.db import FormattedMapping


def colordiff(a: str, b: str) -> tuple[str, str]:
    """Intelligently highlight the differences between two strings."""
    before = ""
    after = ""

    matcher = SequenceMatcher(lambda _: False, a, b)
    for op, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        before_part, after_part = a[a_start:a_end], b[b_start:b_end]
        if op in {"delete", "replace"}:
            before_part = colorize("text_diff_removed", before_part)
        if op in {"insert", "replace"}:
            after_part = colorize("text_diff_added", after_part)

        before += before_part
        after += after_part

    return before, after


FLOAT_EPSILON = 0.01


def _multi_value_diff(field: str, oldset: set[str], newset: set[str]) -> str:
    added = newset - oldset
    removed = oldset - newset

    parts = [
        f"{field}:",
        *(colorize("text_diff_removed", f"  - {i}") for i in sorted(removed)),
        *(colorize("text_diff_added", f"  + {i}") for i in sorted(added)),
    ]
    return "\n".join(parts)


def _field_diff(
    field: str, old: FormattedMapping, new: FormattedMapping
) -> str | None:
    """Given two Model objects and their formatted views, format their values
    for `field` and highlight changes among them. Return a human-readable
    string. If the value has not changed, return None instead.
    """
    # If no change, abort.
    if (oldval := old.model.get(field)) == (newval := new.model.get(field)) or (
        isinstance(oldval, float)
        and isinstance(newval, float)
        and abs(oldval - newval) < FLOAT_EPSILON
    ):
        return None

    if isinstance(oldval, list):
        if (oldset := set(oldval)) != (newset := set(newval)):
            return _multi_value_diff(field, oldset, newset)
        return None

    # Get formatted values for output.
    oldstr, newstr = old.get(field, ""), new.get(field, "")
    if field not in new:
        return colorize("text_diff_removed", f"{field}: {oldstr}")

    if field not in old:
        return colorize("text_diff_added", f"{field}: {newstr}")

    # For strings, highlight changes. For others, colorize the whole thing.
    if isinstance(oldval, str):
        oldstr, newstr = colordiff(oldstr, newstr)
    else:
        oldstr = colorize("text_diff_removed", oldstr)
        newstr = colorize("text_diff_added", newstr)

    return f"{field}: {oldstr} -> {newstr}"
