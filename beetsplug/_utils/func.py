from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


def apply_transforms(text: str, methods: Iterable[Callable[[str], str]]) -> str:
    for method in methods:
        text = method(text)

    return text
