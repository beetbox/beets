from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import pylast
from pylast import _extract, _number

from beets import config, plugins, ui
from beets.dbcore import types
from beets.exceptions import UserError

from ._utils.playcount import update_play_counts

if TYPE_CHECKING:
    import optparse

    from beets.library import Library
    from beets.logging import BeetsLogger as Logger

    from ._utils.playcount import Track

API_URL = "https://ws.audioscrobbler.com/2.0/"


class OurTrack(pylast.Track):
    mbid: str


class OurTopItem(NamedTuple):
    item: OurTrack
    weight: float


class LastImportPlugin(plugins.BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        config["lastfm"].add({"user": "", "api_key": plugins.LASTFM_KEY})
        config["lastfm"]["user"].redact = True
        config["lastfm"]["api_key"].redact = True
        self.config.add({"per_page": 500, "retry_limit": 3})
        self.item_types = {"lastfm_play_count": types.INTEGER}

    def commands(self) -> list[ui.Subcommand]:
        cmd = ui.Subcommand("lastimport", help="import last.fm play-count")

        def func(lib: Library, opts: optparse.Values, args: list[str]) -> None:
            import_lastfm(lib, self._log)

        cmd.func = func
        return [cmd]


class CustomUser(pylast.User):
    """Custom user class derived from pylast.User, and overriding the
    _get_things method to return MBID and album. Also introduces new
    get_top_tracks_by_page method to allow access to more than one page of top
    tracks.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def _get_things(
        self,
        method: str,
        thing_type: type[pylast.Track | pylast.Album],
        params: type[pylast._Opus] | None = None,
        cacheable: bool = True,
        stream: bool = False,
    ) -> tuple[list[OurTopItem], int]:
        """Returns a list of the most played thing_types by this thing, in a
        tuple with the total number of pages of results. Includes an MBID, if
        found.
        """
        doc = self._request(f"{self.ws_prefix}.{method}", cacheable, params)

        toptracks_node = doc.getElementsByTagName("toptracks")[0]
        total_pages = int(toptracks_node.getAttribute("totalPages"))

        seq = []
        for node in doc.getElementsByTagName(thing_type.__name__.lower()):
            title = _extract(node, "name")
            artist = _extract(node, "name", 1)
            mbid = _extract(node, "mbid")
            playcount = _number(_extract(node, "playcount"))

            thing = OurTrack(artist, title, self.network)
            thing.mbid = mbid  # type: ignore[union-attr]
            seq.append(OurTopItem(thing, playcount))

        return seq, total_pages

    def get_top_tracks_by_page(
        self,
        period: str = pylast.PERIOD_OVERALL,
        limit: int | None = None,
        page: int = 1,
        cacheable: bool = True,
    ) -> tuple[list[OurTopItem], int]:
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

        return self._get_things("getTopTracks", pylast.Track, params, cacheable)


def import_lastfm(lib: Library, log: Logger) -> None:
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

        for retry in range(retry_limit):
            tracks, page_total = fetch_tracks(user, page_current + 1, per_page)
            if page_total < 1:
                # It means nothing to us!
                raise UserError("Last.fm reported no data.")

            if tracks:
                found, unknown = update_play_counts(lib, tracks, log, "lastfm")
                found_total += found
                unknown_total += unknown
                break
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


def fetch_tracks(user: str, page: int, limit: int) -> tuple[list[Track], int]:
    network = pylast.LastFMNetwork(api_key=config["lastfm"]["api_key"].get(str))
    user_obj = CustomUser(user, network)
    results, total_pages = user_obj.get_top_tracks_by_page(
        limit=limit, page=page
    )
    return [
        {
            "mbid": t.item.mbid or "",
            "artist": (
                n.strip() if ((a := t.item.artist) and (n := a.name)) else ""
            ),
            "name": ti.strip() if ((i := t.item) and (ti := i.title)) else "",
            "playcount": int(t.weight),
        }
        for t in results
    ], total_pages
