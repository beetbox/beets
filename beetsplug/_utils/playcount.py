from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from beets.dbcore.query import AndQuery, MatchQuery, SubstringQuery

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.library import Library
    from beets.logging import BeetsLogger


class Track(TypedDict):
    mbid: str | None
    name: str | None
    artist: dict[str, str] | None
    album: dict[str, str] | None
    playcount: int


def process_track(lib: Library, track: Track, log: BeetsLogger) -> bool:
    song = None
    trackid = track["mbid"].strip() if track["mbid"] else None
    artist = (
        track["artist"].get("name", "").strip()
        if track["artist"].get("name", "")
        else None
    )
    title = track["name"].strip() if track["name"] else None
    album = ""
    if "album" in track:
        album = (
            track["album"].get("name", "").strip() if track["album"] else None
        )

    log.debug("query: {} - {} ({})", artist, title, album)

    # First try to query by musicbrainz's trackid
    if trackid:
        song = lib.items(MatchQuery("mb_trackid", trackid)).get()

    # If not, try just album/title
    if song is None:
        log.debug(
            "no album match, trying by album/title: {} - {}", album, title
        )
        query = AndQuery(
            [SubstringQuery("album", album), SubstringQuery("title", title)]
        )
        song = lib.items(query).get()

    # If not, try just artist/title
    if song is None:
        log.debug("no album match, trying by artist/title")
        query = AndQuery(
            [SubstringQuery("artist", artist), SubstringQuery("title", title)]
        )
        song = lib.items(query).get()

    # Last resort, try just replacing to utf-8 quote
    if song is None:
        title = title.replace("'", "\u2019")
        log.debug("no title match, trying utf-8 single quote")
        query = AndQuery(
            [SubstringQuery("artist", artist), SubstringQuery("title", title)]
        )
        song = lib.items(query).get()

    if song is not None:
        count = int(song.get("lastfm_play_count", 0))
        new_count = int(track["playcount"])
        log.debug(
            "match: {0.artist} - {0.title} ({0.album}) updating:"
            " lastfm_play_count {1} => {2}",
            song,
            count,
            new_count,
        )
        song["lastfm_play_count"] = new_count
        song.store()
        return True

    log.info("  - No match: {} - {} ({})", artist, title, album)
    return False


def process_tracks(
    lib: Library, tracks: Sequence[Track], log: BeetsLogger
) -> tuple[int, int]:
    total = len(tracks)
    total_found = 0
    total_fails = 0
    log.info("Received {} tracks in this page, processing...", total)

    for track in tracks:
        if process_track(lib, track, log):
            total_found += 1
        else:
            total_fails += 1

    if total_fails > 0:
        log.info(
            "Acquired {}/{} play-counts ({} unknown)",
            total_found,
            total,
            total_fails,
        )

    return total_found, total_fails
