# This file is part of beets.
# Copyright 2025, Sarunas Nejus, Henry Oberholtzer.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Dataclasses for managing artist credits and tracklists from Discogs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, NamedTuple

from beets import config

from .types import Artist, ArtistInfo, Track, TracklistInfo
from .utils import DISAMBIGUATION_RE

if TYPE_CHECKING:
    from beets.autotag.hooks import TrackInfo

    from . import DiscogsPlugin


@dataclass
class ArtistState:
    """Represent Discogs artist credits.

    This object centralizes the plugin's policy for which Discogs artist fields
    to prefer (name vs. ANV), how to treat 'Various', how to format join
    phrases, and how to separate featured artists. It exposes both per-artist
    components and fully joined strings for common tag targets like 'artist' and
    'artist_credit'.
    """

    class ValidArtist(NamedTuple):
        """A normalized, render-ready artist entry extracted from Discogs data.

        Instances represent the subset of Discogs artist information needed for
        tagging, including the join token following the artist and whether the
        entry is considered a featured appearance.
        """

        id: str
        name: str
        credit: str
        join: str
        is_feat: bool

        def get_artist(self, property_name: str) -> str:
            """Return the requested display field with its trailing join token.

            The join token is normalized so commas become ', ' and other join
            phrases are surrounded with spaces, producing a single fragment that
            can be concatenated to form a full artist string.
            """
            join = {",": ", ", "": ""}.get(self.join, f" {self.join} ")
            return f"{getattr(self, property_name)}{join}"

    raw_artists: list[Artist]
    use_anv: bool
    use_credit_anv: bool
    featured_string: str
    should_strip_disambiguation: bool

    @property
    def info(self) -> ArtistInfo:
        """Expose the state in the shape expected by downstream tag mapping."""
        return {k: getattr(self, k) for k in ArtistInfo.__annotations__}  # type: ignore[return-value]

    def strip_disambiguation(self, text: str) -> str:
        """Strip Discogs disambiguation suffixes from an artist or label string.

        This removes Discogs-specific numeric suffixes like 'Name (5)' and can
        be applied to multi-artist strings as well (e.g., 'A (1) & B (2)'). When
        the feature is disabled, the input is returned unchanged.
        """
        if self.should_strip_disambiguation:
            return DISAMBIGUATION_RE.sub("", text)
        return text

    @cached_property
    def valid_artists(self) -> list[ValidArtist]:
        """Build the ordered, filtered list of artists used for rendering.

        The resulting list normalizes Discogs entries by:
        - substituting the configured 'Various Artists' name when Discogs uses
          'Various'
        - choosing between name and ANV according to plugin settings
        - excluding non-empty roles unless they indicate a featured appearance
        - capturing join tokens so the original credit formatting is preserved
        """
        va_name = config["va_name"].as_str()
        return [
            self.ValidArtist(
                str(a["id"]),
                self.strip_disambiguation(anv if self.use_anv else name),
                self.strip_disambiguation(anv if self.use_credit_anv else name),
                a["join"].strip(),
                is_feat,
            )
            for a in self.raw_artists
            if (
                (name := va_name if a["name"] == "Various" else a["name"])
                and (anv := a["anv"] or name)
                and (
                    (is_feat := ("featuring" in a["role"].lower()))
                    or not a["role"]
                )
            )
        ]

    @property
    def artists_ids(self) -> list[str]:
        """Return Discogs artist IDs for all valid artists, preserving order."""
        return [a.id for a in self.valid_artists]

    @property
    def artist_id(self) -> str:
        """Return the primary Discogs artist ID."""
        return self.artists_ids[0]

    @property
    def artists(self) -> list[str]:
        """Return the per-artist display names used for the 'artist' field."""
        return [a.name for a in self.valid_artists]

    @property
    def artists_credit(self) -> list[str]:
        """Return the per-artist display names used for the credit field."""
        return [a.credit for a in self.valid_artists]

    @property
    def artist(self) -> str:
        """Return the fully rendered artist string using display names."""
        return self.join_artists("name")

    @property
    def artist_credit(self) -> str:
        """Return the fully rendered artist credit string."""
        return self.join_artists("credit")

    def join_artists(self, property_name: str) -> str:
        """Render a single artist string with join phrases and featured artists.

        Non-featured artists are concatenated using their join tokens. Featured
        artists are appended after the configured 'featured' marker, preserving
        Discogs order while keeping featured credits separate from the main
        artist string.
        """
        non_featured = [a for a in self.valid_artists if not a.is_feat]
        featured = [a for a in self.valid_artists if a.is_feat]

        artist = "".join(a.get_artist(property_name) for a in non_featured)
        if featured:
            if "feat" not in artist:
                artist += f" {self.featured_string} "

            artist += ", ".join(a.get_artist(property_name) for a in featured)

        return artist

    @classmethod
    def from_plugin(
        cls,
        plugin: DiscogsPlugin,
        artists: list[Artist],
        for_album_artist: bool = False,
    ) -> ArtistState:
        return cls(
            artists,
            plugin.config["anv"][
                "album_artist" if for_album_artist else "artist"
            ].get(bool),
            plugin.config["anv"]["artist_credit"].get(bool),
            plugin.config["featured_string"].as_str(),
            plugin.config["strip_disambiguation"].get(bool),
        )


@dataclass
class TracklistState:
    index: int = 0
    index_tracks: dict[int, str] = field(default_factory=dict)
    tracks: list[TrackInfo] = field(default_factory=list)
    divisions: list[str] = field(default_factory=list)
    next_divisions: list[str] = field(default_factory=list)
    mediums: list[str | None] = field(default_factory=list)
    medium_indices: list[str | None] = field(default_factory=list)

    @property
    def info(self) -> TracklistInfo:
        return asdict(self)  # type: ignore[return-value]

    @classmethod
    def build(
        cls,
        plugin: DiscogsPlugin,
        clean_tracklist: list[Track],
        albumartistinfo: ArtistState,
    ) -> TracklistState:
        state = cls()
        for track in clean_tracklist:
            if track["position"]:
                state.index += 1
                if state.next_divisions:
                    state.divisions += state.next_divisions
                    state.next_divisions.clear()
                track_info, medium, medium_index = plugin.get_track_info(
                    track, state.index, state.divisions, albumartistinfo
                )
                track_info.track_alt = track["position"]
                state.tracks.append(track_info)
                state.mediums.append(medium or None)
                state.medium_indices.append(medium_index or None)
            else:
                state.next_divisions.append(track["title"])
                try:
                    state.divisions.pop()
                except IndexError:
                    pass
                state.index_tracks[state.index + 1] = track["title"]
        return state
