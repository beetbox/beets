from __future__ import annotations

import re
from contextlib import suppress
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from beets.util import unique_list

if TYPE_CHECKING:
    from beets.library import Item

INSTRUMENTAL_LYRICS = "[Instrumental]"
BACKEND_NAMES = {"genius", "musixmatch", "lrclib", "tekstowo"}


@dataclass
class Lyrics:
    """Represent lyrics text together with structured source metadata.

    This value object keeps the canonical lyrics body, optional provenance, and
    optional translation metadata synchronized across fetching, translation, and
    persistence.
    """

    ORIGINAL_PAT = re.compile(r"[^\n]+ / ")
    TRANSLATION_PAT = re.compile(r" / [^\n]+")
    LINE_PARTS_PAT = re.compile(r"^(\[\d\d:\d\d\.\d\d\]|) *(.*)$")

    text: str
    backend: str | None = None
    url: str | None = None
    language: str | None = None
    translation_language: str | None = None
    translations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Populate missing language metadata from the current text."""
        try:
            import langdetect
        except ImportError:
            return

        # Set seed to 0 for deterministic results
        langdetect.DetectorFactory.seed = 0

        if not self.text or self.text == INSTRUMENTAL_LYRICS:
            return

        if not self.language:
            with suppress(langdetect.LangDetectException):
                self.language = langdetect.detect(self.original_text).upper()

        if not self.translation_language:
            all_lines = self.text.splitlines()
            lines_with_delimiter_count = sum(
                1 for ln in all_lines if " / " in ln
            )
            if lines_with_delimiter_count >= len(all_lines) / 2:
                # we are confident we are dealing with translations
                with suppress(langdetect.LangDetectException):
                    self.translation_language = langdetect.detect(
                        self.ORIGINAL_PAT.sub("", self.text)
                    ).upper()

    @classmethod
    def from_legacy_text(cls, text: str) -> Lyrics:
        """Build lyrics from legacy text that may include an inline source."""
        data: dict[str, Any] = {}
        data["text"], *suffix = text.split("\n\nSource: ")
        if suffix:
            url = suffix[0].strip()
            url_root = urlparse(url).netloc.removeprefix("www.").split(".")[0]
            data.update(
                url=url,
                backend=url_root if url_root in BACKEND_NAMES else "google",
            )

        return cls(**data)

    @classmethod
    def from_item(cls, item: Item) -> Lyrics:
        """Build lyrics from an item's canonical text and flexible metadata."""
        data = {"text": item.lyrics}
        for key in ("backend", "url", "language", "translation_language"):
            data[key] = item.get(f"lyrics_{key}", with_album=False)

        return cls(**data)

    @cached_property
    def original_text(self) -> str:
        """Return the original text without translations."""
        # Remove translations from the lyrics text.
        return self.TRANSLATION_PAT.sub("", self.text).strip()

    @cached_property
    def _split_lines(self) -> list[tuple[str, str]]:
        """Split lyrics into timestamp/text pairs for line-wise processing.

        Timestamps, when present, are kept separate so callers can translate or
        normalize text without losing synced timing information.
        """
        return [
            (m[1], m[2]) if (m := self.LINE_PARTS_PAT.match(line)) else ("", "")
            for line in self.text.splitlines()
        ]

    @cached_property
    def timestamps(self) -> list[str]:
        """Return per-line timestamp prefixes from the lyrics text."""
        return [ts for ts, _ in self._split_lines]

    @cached_property
    def text_lines(self) -> list[str]:
        """Return per-line lyric text with timestamps removed."""
        return [ln for _, ln in self._split_lines]

    @property
    def synced(self) -> bool:
        """Return whether the lyrics contain synced timestamp markers."""
        return any(self.timestamps)

    @property
    def translated(self) -> bool:
        """Return whether translation metadata is available."""
        return bool(self.translation_language)

    @property
    def full_text(self) -> str:
        """Return canonical text with translations merged when available."""
        if not self.translations:
            return self.text

        text_pairs = list(zip(self.text_lines, self.translations))

        # only add the separator for non-empty and differing translations
        texts = [" / ".join(unique_list(filter(None, p))) for p in text_pairs]
        # only add the space between non-empty timestamps and texts
        return "\n".join(
            " ".join(filter(None, p)) for p in zip(self.timestamps, texts)
        )
