# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Adds Chromaprint/Acoustid acoustic fingerprinting support to the
autotagger. Requires the pyacoustid library.
"""

from __future__ import annotations

import heapq
import re
from collections import defaultdict
from functools import cached_property, partial
from typing import TYPE_CHECKING

import acoustid
import confuse

from beets import config, ui, util
from beets.autotag.distance import Distance
from beets.metadata_plugins import MetadataSourcePlugin, get_metadata_source
from beets.util.color import colorize

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from beets.autotag.hooks import TrackInfo
    from beets.library.models import Item
    from beetsplug.musicbrainz import MusicBrainzPlugin

API_KEY = "1vOwZtEn"
SCORE_THRESH = 0.5
TRACK_ID_WEIGHT = 10.0
COMMON_REL_THRESH = 0.6  # How many tracks must have an album in common?
MAX_RECORDINGS = 5
MAX_RELEASES = 5

# Stores the Acoustid match information for each track. This is
# populated when an import task begins and then used when searching for
# candidates. It maps audio file paths to (recording_ids, release_ids)
# pairs. If a given path is not present in the mapping, then no match
# was found.
_matches = {}

# Stores the fingerprint and Acoustid ID for each track. This is stored
# as metadata for each track for later use but is not relevant for
# autotagging.
_fingerprints = {}
_acoustids = {}


def prefix(it, count):
    """Truncate an iterable to at most `count` items."""
    for i, v in enumerate(it):
        if i >= count:
            break
        yield v


def releases_key(release, countries, original_year):
    """Used as a key to sort releases by date then preferred country"""
    date = release.get("date")
    if date and original_year:
        year = date.get("year", 9999)
        month = date.get("month", 99)
        day = date.get("day", 99)
    else:
        year = 9999
        month = 99
        day = 99

    # Uses index of preferred countries to sort
    country_key = 99
    if release.get("country"):
        for i, country in enumerate(countries):
            if country.match(release["country"]):
                country_key = i
                break

    return (year, month, day, country_key)


def acoustid_match(log, path):
    """Gets metadata for a file from Acoustid and populates the
    _matches, _fingerprints, and _acoustids dictionaries accordingly.
    """
    try:
        duration, fp = acoustid.fingerprint_file(util.syspath(path))
    except acoustid.FingerprintGenerationError as exc:
        log.error(
            "fingerprinting of {} failed: {}",
            util.displayable_path(repr(path)),
            exc,
        )
        return None
    fp = fp.decode()
    _fingerprints[path] = fp
    try:
        res = acoustid.lookup(
            API_KEY, fp, duration, meta="recordings releases", timeout=10
        )
    except acoustid.AcoustidError as exc:
        log.debug(
            "fingerprint matching {} failed: {}",
            util.displayable_path(repr(path)),
            exc,
        )
        return None
    log.debug("chroma: fingerprinted {}", util.displayable_path(repr(path)))

    # Ensure the response is usable and parse it.
    if res["status"] != "ok" or not res.get("results"):
        log.debug("no match found")
        return None
    result = res["results"][0]  # Best match.
    if result["score"] < SCORE_THRESH:
        log.debug("no results above threshold")
        return None
    _acoustids[path] = result["id"]

    # Get recording and releases from the result
    if not result.get("recordings"):
        log.debug("no recordings found")
        return None
    recording_ids = []
    releases = []
    for recording in result["recordings"]:
        recording_ids.append(recording["id"])
        if "releases" in recording:
            releases.extend(recording["releases"])

    # The releases list is essentially in random order from the Acoustid lookup
    # so we optionally sort it using the match.preferred configuration options.
    # 'original_year' to sort the earliest first and
    # 'countries' to then sort preferred countries first.
    country_patterns = config["match"]["preferred"]["countries"].as_str_seq()
    countries = [re.compile(pat, re.I) for pat in country_patterns]
    original_year = config["match"]["preferred"]["original_year"]
    releases.sort(
        key=partial(
            releases_key, countries=countries, original_year=original_year
        )
    )
    release_ids = [rel["id"] for rel in releases]

    log.debug(
        "matched recordings {} on releases {}", recording_ids, release_ids
    )
    _matches[path] = recording_ids, release_ids


# Plugin structure and autotagging logic.


def _all_releases(items):
    """Given an iterable of Items, determines (according to Acoustid)
    which releases the items have in common. Generates release IDs.
    """
    # Count the number of "hits" for each release.
    relcounts = defaultdict(int)
    for item in items:
        if item.path not in _matches:
            continue

        _, release_ids = _matches[item.path]
        for release_id in release_ids:
            relcounts[release_id] += 1

    for release_id, count in relcounts.items():
        if float(count) / len(items) > COMMON_REL_THRESH:
            yield release_id


class AcoustidPlugin(MetadataSourcePlugin):
    def __init__(self):
        super().__init__()
        self.config.add(
            {
                "auto": True,
            }
        )
        config["acoustid"]["apikey"].redact = True

        if self.config["auto"]:
            self.register_listener("import_task_start", self.fingerprint_task)
        self.register_listener("import_task_apply", apply_acoustid_metadata)

    @cached_property
    def mb(self) -> MusicBrainzPlugin | None:
        """The loaded MusicBrainz plugin, or ``None``.

        Acoustid lookups return MusicBrainz IDs, so chroma needs the
        ``musicbrainz`` plugin to resolve them into album/track
        candidates. When the user has not enabled ``musicbrainz``,
        chroma must not produce any candidates.

        Uses the plugin registry so that any plugin that swaps the
        musicbrainz instance at runtime (e.g. :doc:`plugins/mbpseudo`)
        is respected.
        """
        plugin = get_metadata_source("musicbrainz")
        if plugin is None:
            self._log.debug(
                "musicbrainz plugin not enabled; "
                "acoustid matches will not produce candidates"
            )
        return plugin  # type: ignore[return-value]

    def fingerprint_task(self, task, session):
        return fingerprint_task(self._log, task, session)

    def track_distance(self, item, info):
        dist = Distance()
        if item.path not in _matches or not info.track_id:
            # Match failed or no track ID.
            return dist

        recording_ids, _ = _matches[item.path]
        dist.add_expr("track_id", info.track_id not in recording_ids)
        return dist

    def candidates(self, items, artist, album, va_likely):
        if self.mb is None:
            return []

        albums = []
        for relid in prefix(_all_releases(items), MAX_RELEASES):
            album = self.mb.album_for_id(relid)
            if album:
                albums.append(album)

        self._log.debug("acoustid album candidates: {}", len(albums))
        return albums

    def item_candidates(self, item, artist, title) -> Iterable[TrackInfo]:
        if item.path not in _matches:
            return []

        if self.mb is None:
            return []

        recording_ids, _ = _matches[item.path]
        tracks = []
        for recording_id in prefix(recording_ids, MAX_RECORDINGS):
            track = self.mb.track_for_id(recording_id)
            if track:
                tracks.append(track)
        self._log.debug("acoustid item candidates: {}", len(tracks))
        return tracks

    def album_for_id(self, *args, **kwargs):
        # Lookup by fingerprint ID does not make too much sense.
        return None

    def track_for_id(self, *args, **kwargs):
        # Lookup by fingerprint ID does not make too much sense.
        return None

    def commands(self):
        submit_cmd = ui.Subcommand(
            "submit", help="submit Acoustid fingerprints"
        )

        def submit_cmd_func(lib, opts, args):
            try:
                apikey = config["acoustid"]["apikey"].as_str()
            except confuse.NotFoundError:
                raise ui.UserError("no Acoustid user API key provided")
            submit_items(self._log, apikey, lib.items(args))

        submit_cmd.func = submit_cmd_func

        fingerprint_cmd = ui.Subcommand(
            "fingerprint", help="generate fingerprints for items without them"
        )

        def fingerprint_cmd_func(lib, opts, args):
            for item in lib.items(args):
                fingerprint_item(self._log, item, write=ui.should_write())

        fingerprint_cmd.func = fingerprint_cmd_func

        return [submit_cmd, fingerprint_cmd, self.chromasearch_cmd()]

    def chromasearch_cmd(self):
        cmd = ui.Subcommand(
            "chromasearch", help="search local database by chroma fingerprint"
        )
        cmd.parser.add_path_option()
        cmd.parser.add_format_option()
        cmd.parser.add_option(
            "-s",
            "--search",
            dest="search",
            action="store",
            help="Fingerprint to search for (from the output of fpcalc -plain)",
        )
        cmd.parser.add_option(
            "-c",
            "--count",
            dest="count",
            action="store",
            default=5,
            type=int,
            help="Number of items in result",
        )
        cmd.parser.add_option(
            "--full",
            dest="full",
            action="store_true",
            help="Don't stop searching once we found an exact match",
        )
        cmd.parser.add_option(
            "-w",
            "--write",
            dest="write",
            action="store_true",
            help="Write computed fingerprints to files",
        )

        def search_cmd_func(lib, opts, args):
            if not opts.search:
                raise ui.UserError("no --search provided")
            if opts.count <= 0:
                raise ui.UserError("--count must be > 0")

            target = (0, opts.search.encode("utf-8"))
            top = TopN(opts.count)

            for item in lib.items(args):
                fp = fingerprint_item(
                    self._log,
                    item,
                    write=ui.should_write(opts.write),
                    quiet=True,
                )
                if fp is None:
                    self._log.warning(f"{item}: could not compute fingerprint")
                    continue

                score = acoustid.compare_fingerprints(
                    target, (0, fp.encode("utf-8"))
                )

                if score == 1 and not opts.full:
                    ui.print_(
                        f"{colorize('text_success', 'Found exact match')}: {item}"
                    )
                    return

                if score > 0:
                    top.add(ScoredItem(item, score))

            for item in top:
                ui.print_(str(item))

        cmd.func = search_cmd_func

        return cmd


# Hooks into import process.


def fingerprint_task(log, task, session):
    """Fingerprint each item in the task for later use during the
    autotagging candidate search.
    """
    items = task.items if task.is_album else [task.item]
    for item in items:
        acoustid_match(log, item.path)


def apply_acoustid_metadata(task, session):
    """Apply Acoustid metadata (fingerprint and ID) to the task's items."""
    for item in task.imported_items():
        if item.path in _fingerprints:
            item.acoustid_fingerprint = _fingerprints[item.path]
        if item.path in _acoustids:
            item.acoustid_id = _acoustids[item.path]


# UI commands.


def submit_items(log, userkey, items, chunksize=64):
    """Submit fingerprints for the items to the Acoustid server."""
    data = []  # The running list of dictionaries to submit.

    def submit_chunk():
        """Submit the current accumulated fingerprint data."""
        log.info("submitting {} fingerprints", len(data))
        try:
            acoustid.submit(API_KEY, userkey, data, timeout=10)
        except acoustid.AcoustidError as exc:
            log.warning("acoustid submission error: {}", exc)
        del data[:]

    for item in items:
        fp = fingerprint_item(log, item, write=ui.should_write())

        # Construct a submission dictionary for this item.
        item_data = {
            "duration": int(item.length),
            "fingerprint": fp,
        }
        if item.mb_trackid:
            item_data["mbid"] = item.mb_trackid
            log.debug("submitting MBID")
        else:
            item_data.update(
                {
                    "track": item.title,
                    "artist": item.artist,
                    "album": item.album,
                    "albumartist": item.albumartist,
                    "year": item.year,
                    "trackno": item.track,
                    "discno": item.disc,
                }
            )
            log.debug("submitting textual metadata")
        data.append(item_data)

        # If we have enough data, submit a chunk.
        if len(data) >= chunksize:
            submit_chunk()

    # Submit remaining data in a final chunk.
    if data:
        submit_chunk()


def fingerprint_item(log, item, write=False, quiet=False):
    """Get the fingerprint for an Item. If the item already has a
    fingerprint, it is not regenerated. If fingerprint generation fails,
    return None. If the items are associated with a library, they are
    saved to the database. If `write` is set, then the new fingerprints
    are also written to files' metadata.
    """
    # Get a fingerprint and length for this track.
    if not item.length:
        log.info("{.filepath}: no duration available", item)
    elif item.acoustid_fingerprint:
        if not quiet:
            if write:
                log.info("{.filepath}: fingerprint exists, skipping", item)
            else:
                log.info("{.filepath}: using existing fingerprint", item)
        return item.acoustid_fingerprint
    else:
        log.info("{.filepath}: fingerprinting", item)
        try:
            _, fp = acoustid.fingerprint_file(util.syspath(item.path))
            item.acoustid_fingerprint = fp.decode()
            if write:
                log.info("{.filepath}: writing fingerprint", item)
                item.try_write()
            if item._db:
                item.store()
            return item.acoustid_fingerprint
        except acoustid.FingerprintGenerationError as exc:
            log.info("fingerprint generation failed: {}", exc)


# Classes for search.


class ScoredItem:
    def __init__(self, item: Item, score: float):
        self.item = item
        self.score = score

    def __lt__(self, other):
        return self.score < other.score

    def __gt__(self, other):
        return self.score > other.score

    def __str__(self):
        percent = f"{round(self.score * 100, 2)}%".rjust(6)
        if self.score >= 0.95:
            percent = colorize("text_success", percent)
        elif self.score >= 0.85:
            percent = colorize("text_warning", percent)
        else:
            percent = colorize("text_error", percent)

        return f"[{percent}] {self.item}"


class TopN:
    def __init__(self, n: int):
        self.n = n
        self.heap: list[ScoredItem] = []

    def add(self, value: ScoredItem):
        if len(self.heap) < self.n:
            heapq.heappush(self.heap, value)
        else:
            if value > self.heap[0]:
                heapq.heapreplace(self.heap, value)

    def __iter__(self) -> Iterator[ScoredItem]:
        return iter(sorted(self.heap, reverse=True))
