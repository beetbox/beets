# This file is part of beets.
# Copyright 2016, Rafael Bodill https://github.com/rafi
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

from __future__ import annotations

from typing import TYPE_CHECKING

import pylast
from pylast import TopItem, _extract, _number

from beets import config, plugins, ui
from beets.dbcore import types
from beets.exceptions import UserError

from ._utils.playcount import update_play_counts

if TYPE_CHECKING:
    from ._utils.playcount import Track

API_URL = "https://ws.audioscrobbler.com/2.0/"


class LastImportPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super().__init__()
        config["lastfm"].add(
            {
                "user": "",
                "api_key": plugins.LASTFM_KEY,
            }
        )
        config["lastfm"]["user"].redact = True
        config["lastfm"]["api_key"].redact = True
        self.config.add(
            {
                "per_page": 500,
                "retry_limit": 3,
            }
        )
        self.item_types = {
            "lastfm_play_count": types.INTEGER,
        }

    def commands(self):
        cmd = ui.Subcommand("lastimport", help="import last.fm play-count")

        def func(lib, opts, args):
            import_lastfm(lib, self._log)

        cmd.func = func
        return [cmd]


class CustomUser(pylast.User):
    """Custom user class derived from pylast.User, and overriding the
    _get_things method to return MBID and album. Also introduces new
    get_top_tracks_by_page method to allow access to more than one page of top
    tracks.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _get_things(
        self, method, thing, thing_type, params=None, cacheable=True
    ):
        """Returns a list of the most played thing_types by this thing, in a
        tuple with the total number of pages of results. Includes an MBID, if
        found.
        """
        doc = self._request(f"{self.ws_prefix}.{method}", cacheable, params)

        toptracks_node = doc.getElementsByTagName("toptracks")[0]
        total_pages = int(toptracks_node.getAttribute("totalPages"))

        seq = []
        for node in doc.getElementsByTagName(thing):
            title = _extract(node, "name")
            artist = _extract(node, "name", 1)
            mbid = _extract(node, "mbid")
            playcount = _number(_extract(node, "playcount"))

            thing = thing_type(artist, title, self.network)
            thing.mbid = mbid
            seq.append(TopItem(thing, playcount))

        return seq, total_pages

    def get_top_tracks_by_page(
        self, period=pylast.PERIOD_OVERALL, limit=None, page=1, cacheable=True
    ):
        """Returns the top tracks played by a user, in a tuple with the total
        number of pages of results.
        * period: The period of time. Possible values:
          o PERIOD_OVERALL
          o PERIOD_7DAYS
          o PERIOD_1MONTH
          o PERIOD_3MONTHS
          o PERIOD_6MONTHS
          o PERIOD_12MONTHS
        """

        params = self._get_params()
        params["period"] = period
        params["page"] = page
        if limit:
            params["limit"] = limit

        return self._get_things(
            "getTopTracks", "track", pylast.Track, params, cacheable
        )


def import_lastfm(lib, log):
    user = config["lastfm"]["user"].as_str()
    per_page = config["lastimport"]["per_page"].get(int)

    if not user:
        raise UserError("You must specify a user name for lastimport")

    log.info("Fetching last.fm library for @{}", user)

    page_total = 1
    page_current = 0
    found_total = 0
    unknown_total = 0
    retry_limit = config["lastimport"]["retry_limit"].get(int)
    # Iterate through a yet to be known page total count
    while page_current < page_total:
        log.info(
            "Querying page #{}{}...",
            page_current + 1,
            f"/{page_total}" if page_total > 1 else "",
        )

        for retry in range(0, retry_limit):
            tracks, page_total = fetch_tracks(user, page_current + 1, per_page)
            if page_total < 1:
                # It means nothing to us!
                raise UserError("Last.fm reported no data.")

            if tracks:
                found, unknown = update_play_counts(lib, tracks, log, "lastfm")
                found_total += found
                unknown_total += unknown
                break
            else:
                log.error("ERROR: unable to read page #{}", page_current + 1)
                if retry < retry_limit:
                    log.info(
                        "Retrying page #{}... ({}/{} retry)",
                        page_current + 1,
                        retry + 1,
                        retry_limit,
                    )
                else:
                    log.error(
                        "FAIL: unable to fetch page #{}, ",
                        "tried {} times",
                        page_current,
                        retry + 1,
                    )
        page_current += 1

    log.info("... done!")
    log.info("finished processing {} song pages", page_total)
    log.info("{} unknown play-counts", unknown_total)
    log.info("{} play-counts imported", found_total)


def fetch_tracks(user, page, limit) -> tuple[list[Track], int]:
    network = pylast.LastFMNetwork(api_key=config["lastfm"]["api_key"].get(str))
    user_obj = CustomUser(user, network)
    results, total_pages = user_obj.get_top_tracks_by_page(
        limit=limit, page=page
    )
    return [
        {
            "mbid": track.item.mbid or "",
            "artist": track.item.artist.name.strip(),
            "name": track.item.title.strip(),
            "playcount": int(track.weight),
        }
        for track in results
    ], total_pages
