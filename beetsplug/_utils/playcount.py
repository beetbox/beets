from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from typing_extensions import NotRequired

from beets.dbcore.query import AndQuery, MatchQuery, OrQuery, SubstringQuery

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.dbcore.query import Query
    from beets.library import Item, Library
    from beets.logging import BeetsLogger


class Track(TypedDict):
    mbid: str | None
    name: str
    artist: str
    playcount: int
    album: NotRequired[str | None]


def get_items(lib: Library, track: Track, log: BeetsLogger) -> Sequence[Item]:
    mbid, artist, title = track["mbid"], track["artist"], track["name"]
    album = track.get("album") or ""

    log.debug("query: {} - {} ({})", artist, title, album)

    title_query = OrQuery(
        [
            SubstringQuery("title", title),
            # try a right single quotation mark instead of an apostrophe
            SubstringQuery("title", title.replace("'", "\u2019")),
        ]
    )
    or_queries: list[Query] = [
        AndQuery([SubstringQuery("artist", artist), title_query])
    ]
    # First try to query by musicbrainz's trackid
    if mbid:
        or_queries.append(MatchQuery("mb_trackid", mbid))
    if album:
        or_queries.append(
            AndQuery([SubstringQuery("album", album), title_query])
        )

    return list(lib.items(OrQuery(or_queries)))


def process_track(
    lib: Library, track: Track, log: BeetsLogger, source: str
) -> bool:
    items = get_items(lib, track, log)
    if not items:
        return False

    new_count = track["playcount"]
    field = f"{source}_play_count"
    for song in items:
        count = int(song.get(field, 0))
        log.debug(
            "match: {0.artist} - {0.title} ({0.album}) updating:"
            " {1} {2} => {3}",
            song,
            field,
            count,
            new_count,
        )
        song[field] = new_count
        song.store()

    return True


def update_play_counts(
    lib: Library, tracks: Sequence[Track], log: BeetsLogger, source: str
) -> tuple[int, int]:
    total = len(tracks)
    total_found = 0
    total_fails = 0
    log.info("Received {} tracks in this page, processing...", total)

    with lib.transaction():
        for i, track in enumerate(tracks, 1):
            if i % 250 == 0:
                log.info("Processing track {}/{} ...", i, total)
            if process_track(lib, track, log, source):
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
