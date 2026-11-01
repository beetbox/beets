"""Music theory utilities: key normalization and Circle of Fifths ordering."""

from __future__ import annotations

import re
from functools import cache

# Flat-to-sharp enharmonic equivalents. Keys are lowercase regex patterns;
# values are the canonical sharp equivalents. Used by normalize_key().
ENHARMONIC: dict[str, str] = {
    r"db": "c#",
    r"eb": "d#",
    r"gb": "f#",
    r"ab": "g#",
    r"bb": "a#",
}

# Keys in Circle of Fifths order, using canonical sharp-based notation
# (as produced by normalize_key()). Each major key is directly followed by
# its relative minor, so harmonically compatible keys sort next to each other.
CIRCLE_OF_FIFTHS: tuple[str, ...] = (
    "C",
    "Am",
    "G",
    "Em",
    "D",
    "Bm",
    "A",
    "F#m",
    "E",
    "C#m",
    "B",
    "G#m",
    "F#",
    "D#m",
    "C#",
    "A#m",
    "G#",
    "Fm",
    "D#",
    "Cm",
    "A#",
    "Gm",
    "F",
    "Dm",
)

_UNKNOWN: int = len(CIRCLE_OF_FIFTHS)

# Spelled-out mode suffixes accepted by normalize_key(), longest first so the
# regex alternation prefers ``minor`` over ``min``. Also used by
# key_spellings().
_MINOR_NAMES = ("minor", "min")
_MAJOR_NAMES = ("major", "maj")
_MINOR_WORDS = "|".join(_MINOR_NAMES)
_MAJOR_WORDS = "|".join(_MAJOR_NAMES)


def normalize_key(key: str) -> str:
    """Normalize a musical key string to canonical form.

    Applies flat-to-sharp enharmonic conversion, handles ``minor``/``major``
    suffixes (including the short ``min``/``maj`` forms), and capitalizes the
    result. This helper is the single source of truth for key normalization
    and is used by ``beets.dbcore.types.MusicalKey.parse()``.

    Examples::

        normalize_key("Db")   == "C#"
        normalize_key("A minor") == "Am"
        normalize_key("F# major") == "F#"
        normalize_key("Gmin") == "Gm"
    """
    key = key.lower()
    for flat, sharp in ENHARMONIC.items():
        key = re.sub(flat, sharp, key)
    key = re.sub(rf"([a-g]#?)[\W\s]*(?:{_MINOR_WORDS})\b", r"\1m", key)
    key = re.sub(rf"([a-g]#?)[\W\s]*(?:{_MAJOR_WORDS})\b", r"\1", key)
    return key.capitalize()


_MAJOR_SUFFIXES = ("", *_MAJOR_NAMES, *(f" {n}" for n in _MAJOR_NAMES))
_MINOR_SUFFIXES = ("m", *_MINOR_NAMES, *(f" {n}" for n in _MINOR_NAMES))
_FLAT_OF = {sharp: flat for flat, sharp in ENHARMONIC.items()}


@cache
def key_spellings() -> dict[str, int]:
    """Map each lowercase key spelling recognized by harmonic sorting to its
    Circle of Fifths position.

    Covers sharp and flat tonics with a bare, ``m``, ``maj``/``min`` or
    ``major``/``minor`` suffix, optionally separated from the tonic by a single
    space. Both the SQL ``ORDER BY`` and the Python fallback look keys up in
    this table, so they always agree. Other spellings that
    :func:`normalize_key` accepts (e.g. ``G-minor``) are normalized when
    stored and are not matched here.
    """
    spellings: dict[str, int] = {}
    for position, canonical in enumerate(CIRCLE_OF_FIFTHS):
        minor = canonical.endswith("m")
        tonic = canonical.removesuffix("m").lower()
        suffixes = _MINOR_SUFFIXES if minor else _MAJOR_SUFFIXES
        for name in {tonic, _FLAT_OF.get(tonic, tonic)}:
            for suffix in suffixes:
                spellings[name + suffix] = position
    return spellings


def harmonic_sort_key(key: str | None) -> int:
    """Return the Circle of Fifths position index for harmonic sorting.

    Looks the key up in :func:`key_spellings`, so flat and short spellings
    resolve like their canonical keys. Keys that are not recognized, including
    ``None`` or empty strings, sort to the end (index
    ``len(CIRCLE_OF_FIFTHS)``).
    """
    if not key:
        return _UNKNOWN
    return key_spellings().get(key.lower(), _UNKNOWN)
