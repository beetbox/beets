"""This module contains helpers to build URLs for external sources.

There're currently explicit database fields for musicbrainz (``mb_*``) and deezer
(``deezer_*``), which hold IDs that point to sources.

Since not all data sources have their own fields though, a workaround was needed.
For those sources, the ``mb_*`` musicbrainz fields are overloaded and used for
other non-musicbrainz ids, such as beatport track ids or spotify album ids.

To distinquish, what kind of IDs we're actually looking at the ``data_source`` field
is used. If ``data_source`` is not set, we default to `musicbrainz`.

The ``discogs_*`` fields are **not** overloaded and always expected to point to discogs.
"""

from __future__ import annotations

# Since the ``mb_*`` fields were originally MusicBrainz IDs, they should also be used
# as such, when the no ``data_source`` is set.
DEFAULT_SOURCE = "musicbrainz"

# Album/release web pages for each known data source.
ALBUM_URL_BY_SOURCE: dict[str, str] = {
    "musicbrainz": "https://musicbrainz.org/release/{}",
    "spotify": "https://open.spotify.com/album/{}",
    "deezer": "https://www.deezer.com/album/{}",
    "beatport": "https://www.beatport.com/release/_/{}",
    "tidal": "https://tidal.com/browse/album/{}",
    "discogs": "https://www.discogs.com/release/{}",
}

# Track/recording web pages for each known data source.
#
# Discogs is intentionally absent, as it has no per-track URLs.
TRACK_URL_BY_SOURCE: dict[str, str] = {
    "musicbrainz": "https://musicbrainz.org/recording/{}",
    "spotify": "https://open.spotify.com/track/{}",
    "deezer": "https://www.deezer.com/track/{}",
    "beatport": "https://www.beatport.com/track/_/{}",
    "tidal": "https://tidal.com/browse/track/{}",
}

# Artist web pages for each known data source.
ARTIST_URL_BY_SOURCE: dict[str, str] = {
    "musicbrainz": "https://musicbrainz.org/artist/{}",
    "spotify": "https://open.spotify.com/artist/{}",
    "deezer": "https://www.deezer.com/artist/{}",
    "tidal": "https://tidal.com/browse/artist/{}",
    "discogs": "https://www.discogs.com/artist/{}",
}

# Fields that always point to MusicBrainz, regardless of ``data_source``.
_MB_ONLY_URLS: dict[str, str] = {
    "mb_releasetrackid": "https://musicbrainz.org/track/{}",
    "mb_releasegroupid": "https://musicbrainz.org/release-group/{}",
    "mb_workid": "https://musicbrainz.org/work/{}",
}

# Fields that always point to Discogs, regardless of ``data_source``.
_DISCOGS_ONLY_URLS: dict[str, str] = {
    "discogs_albumid": "https://www.discogs.com/release/{}",
    "discogs_artistid": "https://www.discogs.com/artist/{}",
    "discogs_labelid": "https://www.discogs.com/label/{}",
}


def _format(templates: dict[str, str], source: str | None, value) -> str | None:
    """Small helper function to get an url by source from one of the lookup maps."""
    if not value:
        return None

    template = templates.get((source or DEFAULT_SOURCE).lower())
    return template.format(value) if template else None


def album_url(source: str | None, album_id) -> str | None:
    """URL for an album/release on ``source`` (defaults to MusicBrainz)."""
    return _format(ALBUM_URL_BY_SOURCE, source, album_id)


def track_url(source: str | None, track_id) -> str | None:
    """URL for a track/recording on ``source`` (defaults to MusicBrainz).

    Returns ``None`` for sources without per-track URLs (Discogs).
    """
    return _format(TRACK_URL_BY_SOURCE, source, track_id)


def artist_url(source: str | None, artist_id) -> str | None:
    """URL for an artist on ``source`` (defaults to MusicBrainz)."""
    return _format(ARTIST_URL_BY_SOURCE, source, artist_id)


def field_url(field: str, value, source: str | None = None) -> str | None:
    """Resolve a beets ID field to a URL, taking ``data_source`` into account.

    Returns ``None`` if the ``field`` is not a known external-ID field or
    the source is unknown.
    """
    if not value:
        return None

    if field == "mb_albumid":
        return album_url(source, value)
    if field == "mb_trackid":
        return track_url(source, value)
    if field in ("mb_artistid", "mb_albumartistid"):
        return artist_url(source, value)

    if template := _MB_ONLY_URLS.get(field):
        return template.format(value)
    if template := _DISCOGS_ONLY_URLS.get(field):
        return template.format(value)

    return None
