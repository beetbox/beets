from __future__ import annotations

from enum import Enum

from typing_extensions import Self


class Action(Enum):
    """Enumeration of possible actions for an import task."""

    SKIP = "SKIP"
    ASIS = "ASIS"
    TRACKS = "TRACKS"
    APPLY = "APPLY"
    ALBUMS = "ALBUMS"
    RETAG = "RETAG"
    # The RETAG action represents "don't apply any match, but do record
    # new metadata". It's not reachable via the standard command prompt but
    # can be used by plugins.


class DuplicateAction(str, Enum):
    text: str

    def __new__(cls, code: str, text: str) -> Self:
        obj = str.__new__(cls, code)
        obj._value_ = code
        obj.text = text
        return obj

    @classmethod
    def options(cls) -> list[str]:
        return [d.text for d in cls]

    @classmethod
    def strict_options(cls) -> list[str]:
        return [d.text for d in set(cls) - {DuplicateAction.ASK}]

    @classmethod
    def choices(cls) -> dict[str, str]:
        return {d.name.lower(): d.value for d in cls}

    SKIP = "s", "Skip new"
    MERGE = "m", "Merge all"
    REMOVE = "r", "Remove old"
    KEEP = "k", "Keep all"
    ASK = "a", "Ask"
