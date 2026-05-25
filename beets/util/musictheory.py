"""Music theory utilities: key normalization and Circle of Fifths ordering."""

from __future__ import annotations

import re

# Flat-to-sharp enharmonic equivalents. Keys are lowercase regex patterns;
# values are the canonical sharp equivalents. Used by normalize_key() and
# referenced by beets.dbcore.types.MusicalKey.
ENHARMONIC: dict[str, str] = {
    r"db": "c#",
    r"eb": "d#",
    r"gb": "f#",
    r"ab": "g#",
    r"bb": "a#",
}

# Keys in Circle of Fifths order, using canonical sharp-based notation
# (as produced by normalize_key()). Major keys first, then their relative
# minors at the matching positions.
CIRCLE_OF_FIFTHS: tuple[str, ...] = (
    # Major keys
    "C",
    "G",
    "D",
    "A",
    "E",
    "B",
    "F#",
    "C#",
    "G#",
    "D#",
    "A#",
    "F",
    # Relative minor keys
    "Am",
    "Em",
    "Bm",
    "F#m",
    "C#m",
    "G#m",
    "D#m",
    "A#m",
    "Fm",
    "Cm",
    "Gm",
    "Dm",
)

_POSITION: dict[str, int] = {k: i for i, k in enumerate(CIRCLE_OF_FIFTHS)}
_UNKNOWN: int = len(CIRCLE_OF_FIFTHS)


def normalize_key(key: str) -> str:
    """Normalize a musical key string to canonical form.

    Applies flat-to-sharp enharmonic conversion, handles ``minor``/``major``
    suffixes, and capitalizes the result. Mirrors the logic in
    ``beets.dbcore.types.MusicalKey.parse()``.

    Examples::

        normalize_key("Db")   == "C#"
        normalize_key("A minor") == "Am"
        normalize_key("F# major") == "F#"
    """
    key = key.lower()
    for flat, sharp in ENHARMONIC.items():
        key = re.sub(flat, sharp, key)
    key = re.sub(r"([a-g]#?)[\W\s]+minor", r"\1m", key)
    key = re.sub(r"([a-g]#?)[\W\s]+major", r"\1", key)
    return key.capitalize()


def harmonic_sort_key(key: str | None) -> int:
    """Return the Circle of Fifths position index for harmonic sorting.

    Applies enharmonic normalization before lookup, so flat variants (e.g.
    ``Db``) resolve correctly to their sharp equivalent (``C#``).  Keys not
    present in :data:`CIRCLE_OF_FIFTHS` — including ``None`` or empty strings
    — sort to the end (index ``len(CIRCLE_OF_FIFTHS)``).
    """
    if not key:
        return _UNKNOWN
    return _POSITION.get(normalize_key(key), _UNKNOWN)
