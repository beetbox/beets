from beets import dbcore


def process_tracks(lib, tracks, log):
    total = len(tracks)
    total_found = 0
    total_fails = 0
    log.info("Received {} tracks in this page, processing...", total)

    for num in range(0, total):
        song = None
        trackid = tracks[num]["mbid"].strip() if tracks[num]["mbid"] else None
        artist = (
            tracks[num]["artist"].get("name", "").strip()
            if tracks[num]["artist"].get("name", "")
            else None
        )
        title = tracks[num]["name"].strip() if tracks[num]["name"] else None
        album = ""
        if "album" in tracks[num]:
            album = (
                tracks[num]["album"].get("name", "").strip()
                if tracks[num]["album"]
                else None
            )

        log.debug("query: {} - {} ({})", artist, title, album)

        # First try to query by musicbrainz's trackid
        if trackid:
            song = lib.items(
                dbcore.query.MatchQuery("mb_trackid", trackid)
            ).get()

        # If not, try just album/title
        if song is None:
            log.debug(
                "no album match, trying by album/title: {} - {}", album, title
            )
            query = dbcore.AndQuery(
                [
                    dbcore.query.SubstringQuery("album", album),
                    dbcore.query.SubstringQuery("title", title),
                ]
            )
            song = lib.items(query).get()

        # If not, try just artist/title
        if song is None:
            log.debug("no album match, trying by artist/title")
            query = dbcore.AndQuery(
                [
                    dbcore.query.SubstringQuery("artist", artist),
                    dbcore.query.SubstringQuery("title", title),
                ]
            )
            song = lib.items(query).get()

        # Last resort, try just replacing to utf-8 quote
        if song is None:
            title = title.replace("'", "\u2019")
            log.debug("no title match, trying utf-8 single quote")
            query = dbcore.AndQuery(
                [
                    dbcore.query.SubstringQuery("artist", artist),
                    dbcore.query.SubstringQuery("title", title),
                ]
            )
            song = lib.items(query).get()

        if song is not None:
            count = int(song.get("lastfm_play_count", 0))
            new_count = int(tracks[num]["playcount"])
            log.debug(
                "match: {0.artist} - {0.title} ({0.album}) updating:"
                " lastfm_play_count {1} => {2}",
                song,
                count,
                new_count,
            )
            song["lastfm_play_count"] = new_count
            song.store()
            total_found += 1
        else:
            total_fails += 1
            log.info("  - No match: {} - {} ({})", artist, title, album)

    if total_fails > 0:
        log.info(
            "Acquired {}/{} play-counts ({} unknown)",
            total_found,
            total,
            total_fails,
        )

    return total_found, total_fails
