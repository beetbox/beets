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

"""Searches for albums in the MusicBrainz database."""

from __future__ import annotations

import traceback
from collections import Counter
from contextlib import suppress
from functools import cached_property
from itertools import product
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import musicbrainzngs
from confuse.exceptions import NotFoundError

import beets
import beets.autotag.hooks
from beets import config, plugins, util
from beets.metadata_plugins import MetadataSourcePlugin
from beets.util.id_extractors import extract_release_id

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from typing import Literal

    from beets.library import Item

    from ._typing import JSONDict

VARIOUS_ARTISTS_ID = "89ad4ac3-39f7-470e-963a-56509c546377"

BASE_URL = "https://musicbrainz.org/"

SKIPPED_TRACKS = ["[data track]"]

FIELDS_TO_MB_KEYS = {
    "barcode": "barcode",
    "catalognum": "catno",
    "country": "country",
    "label": "label",
    "media": "format",
    "year": "date",
}

musicbrainzngs.set_useragent("beets", beets.__version__, "https://beets.io/")


class MusicBrainzAPIError(util.HumanReadableError):
    """An error while talking to MusicBrainz. The `query` field is the
    parameter to the action and may have any type.
    """

    def __init__(self, reason, verb, query, tb=None):
        self.query = query
        if isinstance(reason, musicbrainzngs.WebServiceError):
            reason = "MusicBrainz not reachable"
        super().__init__(reason, verb, tb)

    def get_message(self):
        return f"{self._reasonstr()} in {self.verb} with query {self.query!r}"


RELEASE_INCLUDES = list(
    {
        "artists",
        "media",
        "recordings",
        "release-groups",
        "labels",
        "artist-credits",
        "aliases",
        "recording-level-rels",
        "work-rels",
        "work-level-rels",
        "artist-rels",
        "isrcs",
        "url-rels",
        "release-rels",
        "genres",
        "tags",
    }
    & set(musicbrainzngs.VALID_INCLUDES["release"])
)

TRACK_INCLUDES = list(
    {
        "artists",
        "aliases",
        "isrcs",
        "work-level-rels",
        "artist-rels",
    }
    & set(musicbrainzngs.VALID_INCLUDES["recording"])
)

BROWSE_INCLUDES = [
    "artist-credits",
    "work-rels",
    "artist-rels",
    "recording-rels",
    "release-rels",
]
if "work-level-rels" in musicbrainzngs.VALID_BROWSE_INCLUDES["recording"]:
    BROWSE_INCLUDES.append("work-level-rels")
BROWSE_CHUNKSIZE = 100
BROWSE_MAXTRACKS = 500


def _preferred_alias(
    aliases: list[JSONDict], languages: list[str] | None = None
) -> JSONDict | None:
    """Given a list of alias structures for an artist credit, select
    and return the user's preferred alias or None if no matching
    alias is found.
    """
    if not aliases:
        return None

    # Only consider aliases that have locales set.
    valid_aliases = [a for a in aliases if "locale" in a]

    # Get any ignored alias types and lower case them to prevent case issues
    ignored_alias_types = config["import"]["ignored_alias_types"].as_str_seq()
    ignored_alias_types = [a.lower() for a in ignored_alias_types]

    # Search configured locales in order.
    if languages is None:
        languages = config["import"]["languages"].as_str_seq()

    for locale in languages:
        # Find matching primary aliases for this locale that are not
        # being ignored
        matches = []
        for alias in valid_aliases:
            if (
                alias["locale"] == locale
                and "primary" in alias
                and alias.get("type", "").lower() not in ignored_alias_types
            ):
                matches.append(alias)

        # Skip to the next locale if we have no matches
        if not matches:
            continue

        return matches[0]

    return None


def _multi_artist_credit(
    credit: list[JSONDict], include_join_phrase: bool
) -> tuple[list[str], list[str], list[str]]:
    """Given a list representing an ``artist-credit`` block, accumulate
    data into a triple of joined artist name lists: canonical, sort, and
    credit.
    """
    artist_parts = []
    artist_sort_parts = []
    artist_credit_parts = []
    for el in credit:
        if isinstance(el, str):
            # Join phrase.
            if include_join_phrase:
                artist_parts.append(el)
                artist_credit_parts.append(el)
                artist_sort_parts.append(el)

        else:
            alias = _preferred_alias(el["artist"].get("alias-list", ()))

            # An artist.
            if alias:
                cur_artist_name = alias["alias"]
            else:
                cur_artist_name = el["artist"]["name"]
            artist_parts.append(cur_artist_name)

            # Artist sort name.
            if alias:
                artist_sort_parts.append(alias["sort-name"])
            elif "sort-name" in el["artist"]:
                artist_sort_parts.append(el["artist"]["sort-name"])
            else:
                artist_sort_parts.append(cur_artist_name)

            # Artist credit.
            if "name" in el:
                artist_credit_parts.append(el["name"])
            else:
                artist_credit_parts.append(cur_artist_name)

    return (
        artist_parts,
        artist_sort_parts,
        artist_credit_parts,
    )


def track_url(trackid: str) -> str:
    return urljoin(BASE_URL, f"recording/{trackid}")


def _flatten_artist_credit(credit: list[JSONDict]) -> tuple[str, str, str]:
    """Given a list representing an ``artist-credit`` block, flatten the
    data into a triple of joined artist name strings: canonical, sort, and
    credit.
    """
    artist_parts, artist_sort_parts, artist_credit_parts = _multi_artist_credit(
        credit, include_join_phrase=True
    )
    return (
        "".join(artist_parts),
        "".join(artist_sort_parts),
        "".join(artist_credit_parts),
    )


def _artist_ids(credit: list[JSONDict]) -> list[str]:
    """
    Given a list representing an ``artist-credit``,
    return a list of artist IDs
    """
    artist_ids: list[str] = []
    for el in credit:
        if isinstance(el, dict):
            artist_ids.append(el["artist"]["id"])

    return artist_ids


def _get_related_artist_names(relations, relation_type):
    """Given a list representing the artist relationships extract the names of
    the remixers and concatenate them.
    """
    related_artists = []

    for relation in relations:
        if relation["type"] == relation_type:
            related_artists.append(relation["artist"]["name"])

    return ", ".join(related_artists)


def album_url(albumid: str) -> str:
    return urljoin(BASE_URL, f"release/{albumid}")


def _preferred_release_event(
    release: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Given a release, select and return the user's preferred release
    event as a tuple of (country, release_date). Fall back to the
    default release event if a preferred event is not found.
    """
    preferred_countries: Sequence[str] = config["match"]["preferred"][
        "countries"
    ].as_str_seq()

    for country in preferred_countries:
        for event in release.get("release-event-list", {}):
            try:
                if country in event["area"]["iso-3166-1-code-list"]:
                    return country, event["date"]
            except KeyError:
                pass

    return release.get("country"), release.get("date")


def _set_date_str(
    info: beets.autotag.hooks.AlbumInfo,
    date_str: str,
    original: bool = False,
):
    """Given a (possibly partial) YYYY-MM-DD string and an AlbumInfo
    object, set the object's release date fields appropriately. If
    `original`, then set the original_year, etc., fields.
    """
    if date_str:
        date_parts = date_str.split("-")
        for key in ("year", "month", "day"):
            if date_parts:
                date_part = date_parts.pop(0)
                try:
                    date_num = int(date_part)
                except ValueError:
                    continue

                if original:
                    key = f"original_{key}"
                setattr(info, key, date_num)


def _is_translation(r):
    _trans_key = "transl-tracklisting"
    return r["type"] == _trans_key and r["direction"] == "backward"


def _find_actual_release_from_pseudo_release(
    pseudo_rel: JSONDict,
) -> JSONDict | None:
    try:
        relations = pseudo_rel["release"]["release-relation-list"]
    except KeyError:
        return None

    # currently we only support trans(liter)ation's
    translations = [r for r in relations if _is_translation(r)]

    if not translations:
        return None

    actual_id = translations[0]["target"]

    return musicbrainzngs.get_release_by_id(actual_id, RELEASE_INCLUDES)


def _merge_pseudo_and_actual_album(
    pseudo: beets.autotag.hooks.AlbumInfo, actual: beets.autotag.hooks.AlbumInfo
) -> beets.autotag.hooks.AlbumInfo:
    """
    Merges a pseudo release with its actual release.

    This implementation is naive, it doesn't overwrite fields,
    like status or ids.

    According to the ticket PICARD-145, the main release id should be used.
    But the ticket has been in limbo since over a decade now.
    It also suggests the introduction of the tag `musicbrainz_pseudoreleaseid`,
    but as of this field can't be found in any official Picard docs,
    hence why we did not implement that for now.
    """
    merged = pseudo.copy()
    from_actual = {
        k: actual[k]
        for k in [
            "media",
            "mediums",
            "country",
            "catalognum",
            "year",
            "month",
            "day",
            "original_year",
            "original_month",
            "original_day",
            "label",
            "barcode",
            "asin",
            "style",
            "genre",
        ]
    }
    merged.update(from_actual)
    return merged


class MusicBrainzPlugin(MetadataSourcePlugin):
    @cached_property
    def genres_field(self) -> str:
        return f"{self.config['genres_tag'].as_choice(['genre', 'tag'])}-list"

    def __init__(self):
        """Set up the python-musicbrainz-ngs module according to settings
        from the beets configuration. This should be called at startup.
        """
        super().__init__()
        self.config.add(
            {
                "host": "musicbrainz.org",
                "https": False,
                "ratelimit": 1,
                "ratelimit_interval": 1,
                "genres": False,
                "genres_tag": "genre",
                "external_ids": {
                    "discogs": False,
                    "bandcamp": False,
                    "spotify": False,
                    "deezer": False,
                    "tidal": False,
                },
                "extra_tags": [],
            },
        )
        # TODO: Remove in 3.0.0
        with suppress(NotFoundError):
            self.config["search_limit"] = self.config["match"][
                "searchlimit"
            ].get()
            self._log.warning(
                "'musicbrainz.searchlimit' option is deprecated and will be "
                "removed in 3.0.0. Use 'musicbrainz.search_limit' instead."
            )
        hostname = self.config["host"].as_str()
        https = self.config["https"].get(bool)
        # Only call set_hostname when a custom server is configured. Since
        # musicbrainz-ngs connects to musicbrainz.org with HTTPS by default
        if hostname != "musicbrainz.org":
            musicbrainzngs.set_hostname(hostname, https)
        musicbrainzngs.set_rate_limit(
            self.config["ratelimit_interval"].as_number(),
            self.config["ratelimit"].get(int),
        )

    def track_info(
        self,
        recording: JSONDict,
        index: int | None = None,
        medium: int | None = None,
        medium_index: int | None = None,
        medium_total: int | None = None,
    ) -> beets.autotag.hooks.TrackInfo:
        """Translates a MusicBrainz recording result dictionary into a beets
        ``TrackInfo`` object. Three parameters are optional and are used
        only for tracks that appear on releases (non-singletons): ``index``,
        the overall track number; ``medium``, the disc number;
        ``medium_index``, the track's index on its medium; ``medium_total``,
        the number of tracks on the medium. Each number is a 1-based index.
        """
        info = beets.autotag.hooks.TrackInfo(
            title=recording["title"],
            track_id=recording["id"],
            index=index,
            medium=medium,
            medium_index=medium_index,
            medium_total=medium_total,
            data_source=self.data_source,
            data_url=track_url(recording["id"]),
        )

        if recording.get("artist-credit"):
            # Get the artist names.
            (
                info.artist,
                info.artist_sort,
                info.artist_credit,
            ) = _flatten_artist_credit(recording["artist-credit"])

            (
                info.artists,
                info.artists_sort,
                info.artists_credit,
            ) = _multi_artist_credit(
                recording["artist-credit"], include_join_phrase=False
            )

            info.artists_ids = _artist_ids(recording["artist-credit"])
            info.artist_id = info.artists_ids[0]

        if recording.get("artist-relation-list"):
            info.remixer = _get_related_artist_names(
                recording["artist-relation-list"], relation_type="remixer"
            )

        if recording.get("length"):
            info.length = int(recording["length"]) / 1000.0

        info.trackdisambig = recording.get("disambiguation")

        if recording.get("isrc-list"):
            info.isrc = ";".join(recording["isrc-list"])

        lyricist = []
        composer = []
        composer_sort = []
        for work_relation in recording.get("work-relation-list", ()):
            if work_relation["type"] != "performance":
                continue
            info.work = work_relation["work"]["title"]
            info.mb_workid = work_relation["work"]["id"]
            if "disambiguation" in work_relation["work"]:
                info.work_disambig = work_relation["work"]["disambiguation"]

            for artist_relation in work_relation["work"].get(
                "artist-relation-list", ()
            ):
                if "type" in artist_relation:
                    type = artist_relation["type"]
                    if type == "lyricist":
                        lyricist.append(artist_relation["artist"]["name"])
                    elif type == "composer":
                        composer.append(artist_relation["artist"]["name"])
                        composer_sort.append(
                            artist_relation["artist"]["sort-name"]
                        )
        if lyricist:
            info.lyricist = ", ".join(lyricist)
        if composer:
            info.composer = ", ".join(composer)
            info.composer_sort = ", ".join(composer_sort)

        arranger = []
        for artist_relation in recording.get("artist-relation-list", ()):
            if "type" in artist_relation:
                type = artist_relation["type"]
                if type == "arranger":
                    arranger.append(artist_relation["artist"]["name"])
        if arranger:
            info.arranger = ", ".join(arranger)

        # Supplementary fields provided by plugins
        extra_trackdatas = plugins.send("mb_track_extract", data=recording)
        for extra_trackdata in extra_trackdatas:
            info.update(extra_trackdata)

        return info

    def album_info(self, release: JSONDict) -> beets.autotag.hooks.AlbumInfo:
        """Takes a MusicBrainz release result dictionary and returns a beets
        AlbumInfo object containing the interesting data about that release.
        """
        # Get artist name using join phrases.
        artist_name, artist_sort_name, artist_credit_name = (
            _flatten_artist_credit(release["artist-credit"])
        )

        (
            artists_names,
            artists_sort_names,
            artists_credit_names,
        ) = _multi_artist_credit(
            release["artist-credit"], include_join_phrase=False
        )

        ntracks = sum(len(m["track-list"]) for m in release["medium-list"])

        # The MusicBrainz API omits 'artist-relation-list' and 'work-relation-list'
        # when the release has more than 500 tracks. So we use browse_recordings
        # on chunks of tracks to recover the same information in this case.
        if ntracks > BROWSE_MAXTRACKS:
            self._log.debug("Album {} has too many tracks", release["id"])
            recording_list = []
            for i in range(0, ntracks, BROWSE_CHUNKSIZE):
                self._log.debug("Retrieving tracks starting at {}", i)
                recording_list.extend(
                    musicbrainzngs.browse_recordings(
                        release=release["id"],
                        limit=BROWSE_CHUNKSIZE,
                        includes=BROWSE_INCLUDES,
                        offset=i,
                    )["recording-list"]
                )
            track_map = {r["id"]: r for r in recording_list}
            for medium in release["medium-list"]:
                for recording in medium["track-list"]:
                    recording_info = track_map[recording["recording"]["id"]]
                    recording["recording"] = recording_info

        # Basic info.
        track_infos = []
        index = 0
        for medium in release["medium-list"]:
            disctitle = medium.get("title")
            format = medium.get("format")

            if format in config["match"]["ignored_media"].as_str_seq():
                continue

            all_tracks = medium["track-list"]
            if (
                "data-track-list" in medium
                and not config["match"]["ignore_data_tracks"]
            ):
                all_tracks += medium["data-track-list"]
            track_count = len(all_tracks)

            if "pregap" in medium:
                all_tracks.insert(0, medium["pregap"])

            for track in all_tracks:
                if (
                    "title" in track["recording"]
                    and track["recording"]["title"] in SKIPPED_TRACKS
                ):
                    continue

                if (
                    "video" in track["recording"]
                    and track["recording"]["video"] == "true"
                    and config["match"]["ignore_video_tracks"]
                ):
                    continue

                # Basic information from the recording.
                index += 1
                ti = self.track_info(
                    track["recording"],
                    index,
                    int(medium["position"]),
                    int(track["position"]),
                    track_count,
                )
                ti.release_track_id = track["id"]
                ti.disctitle = disctitle
                ti.media = format
                ti.track_alt = track["number"]

                # Prefer track data, where present, over recording data.
                if track.get("title"):
                    ti.title = track["title"]
                if track.get("artist-credit"):
                    # Get the artist names.
                    (
                        ti.artist,
                        ti.artist_sort,
                        ti.artist_credit,
                    ) = _flatten_artist_credit(track["artist-credit"])

                    (
                        ti.artists,
                        ti.artists_sort,
                        ti.artists_credit,
                    ) = _multi_artist_credit(
                        track["artist-credit"], include_join_phrase=False
                    )

                    ti.artists_ids = _artist_ids(track["artist-credit"])
                    ti.artist_id = ti.artists_ids[0]
                if track.get("length"):
                    ti.length = int(track["length"]) / (1000.0)

                track_infos.append(ti)

        album_artist_ids = _artist_ids(release["artist-credit"])
        info = beets.autotag.hooks.AlbumInfo(
            album=release["title"],
            album_id=release["id"],
            artist=artist_name,
            artist_id=album_artist_ids[0],
            artists=artists_names,
            artists_ids=album_artist_ids,
            tracks=track_infos,
            mediums=len(release["medium-list"]),
            artist_sort=artist_sort_name,
            artists_sort=artists_sort_names,
            artist_credit=artist_credit_name,
            artists_credit=artists_credit_names,
            data_source=self.data_source,
            data_url=album_url(release["id"]),
            barcode=release.get("barcode"),
        )
        info.va = info.artist_id == VARIOUS_ARTISTS_ID
        if info.va:
            info.artist = config["va_name"].as_str()
        info.asin = release.get("asin")
        info.releasegroup_id = release["release-group"]["id"]
        info.albumstatus = release.get("status")

        if release["release-group"].get("title"):
            info.release_group_title = release["release-group"].get("title")

        # Get the disambiguation strings at the release and release group level.
        if release["release-group"].get("disambiguation"):
            info.releasegroupdisambig = release["release-group"].get(
                "disambiguation"
            )
        if release.get("disambiguation"):
            info.albumdisambig = release.get("disambiguation")

        # Get the "classic" Release type. This data comes from a legacy API
        # feature before MusicBrainz supported multiple release types.
        if "type" in release["release-group"]:
            reltype = release["release-group"]["type"]
            if reltype:
                info.albumtype = reltype.lower()

        # Set the new-style "primary" and "secondary" release types.
        albumtypes = []
        if "primary-type" in release["release-group"]:
            rel_primarytype = release["release-group"]["primary-type"]
            if rel_primarytype:
                albumtypes.append(rel_primarytype.lower())
        if "secondary-type-list" in release["release-group"]:
            if release["release-group"]["secondary-type-list"]:
                for sec_type in release["release-group"]["secondary-type-list"]:
                    albumtypes.append(sec_type.lower())
        info.albumtypes = albumtypes

        # Release events.
        info.country, release_date = _preferred_release_event(release)
        release_group_date = release["release-group"].get("first-release-date")
        if not release_date:
            # Fall back if release-specific date is not available.
            release_date = release_group_date

        if release_date:
            _set_date_str(info, release_date, False)
        _set_date_str(info, release_group_date, True)

        # Label name.
        if release.get("label-info-list"):
            label_info = release["label-info-list"][0]
            if label_info.get("label"):
                label = label_info["label"]["name"]
                if label != "[no label]":
                    info.label = label
            info.catalognum = label_info.get("catalog-number")

        # Text representation data.
        if release.get("text-representation"):
            rep = release["text-representation"]
            info.script = rep.get("script")
            info.language = rep.get("language")

        # Media (format).
        if release["medium-list"]:
            # If all media are the same, use that medium name
            if len({m.get("format") for m in release["medium-list"]}) == 1:
                info.media = release["medium-list"][0].get("format")
            # Otherwise, let's just call it "Media"
            else:
                info.media = "Media"

        if self.config["genres"]:
            sources = [
                release["release-group"].get(self.genres_field, []),
                release.get(self.genres_field, []),
            ]
            genres: Counter[str] = Counter()
            for source in sources:
                for genreitem in source:
                    genres[genreitem["name"]] += int(genreitem["count"])
            info.genre = "; ".join(
                genre
                for genre, _count in sorted(genres.items(), key=lambda g: -g[1])
            )

        # We might find links to external sources (Discogs, Bandcamp, ...)
        external_ids = self.config["external_ids"].get()
        wanted_sources = {
            site for site, wanted in external_ids.items() if wanted
        }
        if wanted_sources and (url_rels := release.get("url-relation-list")):
            urls = {}

            for source, url in product(wanted_sources, url_rels):
                if f"{source}.com" in (target := url["target"]):
                    urls[source] = target
                    self._log.debug(
                        "Found link to {} release via MusicBrainz",
                        source.capitalize(),
                    )

            for source, url in urls.items():
                setattr(
                    info, f"{source}_album_id", extract_release_id(source, url)
                )

        extra_albumdatas = plugins.send("mb_album_extract", data=release)
        for extra_albumdata in extra_albumdatas:
            info.update(extra_albumdata)

        return info

    @cached_property
    def extra_mb_field_by_tag(self) -> dict[str, str]:
        """Map configured extra tags to their MusicBrainz API field names.

        Process user configuration to determine which additional MusicBrainz
        fields should be included in search queries.
        """
        mb_field_by_tag = {
            t: FIELDS_TO_MB_KEYS[t]
            for t in self.config["extra_tags"].as_str_seq()
            if t in FIELDS_TO_MB_KEYS
        }
        if mb_field_by_tag:
            self._log.debug("Additional search terms: {}", mb_field_by_tag)

        return mb_field_by_tag

    def get_album_criteria(
        self, items: Sequence[Item], artist: str, album: str, va_likely: bool
    ) -> dict[str, str]:
        criteria = {
            "release": album,
            "alias": album,
            "tracks": str(len(items)),
        } | ({"arid": VARIOUS_ARTISTS_ID} if va_likely else {"artist": artist})

        for tag, mb_field in self.extra_mb_field_by_tag.items():
            most_common, _ = util.plurality(i.get(tag) for i in items)
            value = str(most_common)
            if tag == "catalognum":
                value = value.replace(" ", "")

            criteria[mb_field] = value

        return criteria

    def _search_api(
        self,
        query_type: Literal["recording", "release"],
        filters: dict[str, str],
    ) -> list[JSONDict]:
        """Perform MusicBrainz API search and return results.

        Execute a search against the MusicBrainz API for recordings or releases
        using the provided criteria. Handles API errors by converting them into
        MusicBrainzAPIError exceptions with contextual information.
        """
        filters = {
            k: _v for k, v in filters.items() if (_v := v.lower().strip())
        }
        self._log.debug(
            "Searching for MusicBrainz {}s with: {!r}", query_type, filters
        )
        try:
            method = getattr(musicbrainzngs, f"search_{query_type}s")
            res = method(limit=self.config["search_limit"].get(), **filters)
        except musicbrainzngs.MusicBrainzError as exc:
            raise MusicBrainzAPIError(
                exc, f"{query_type} search", filters, traceback.format_exc()
            )
        return res[f"{query_type}-list"]

    def candidates(
        self,
        items: Sequence[Item],
        artist: str,
        album: str,
        va_likely: bool,
    ) -> Iterable[beets.autotag.hooks.AlbumInfo]:
        criteria = self.get_album_criteria(items, artist, album, va_likely)
        release_ids = (r["id"] for r in self._search_api("release", criteria))

        yield from filter(None, map(self.album_for_id, release_ids))

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterable[beets.autotag.hooks.TrackInfo]:
        criteria = {"artist": artist, "recording": title, "alias": title}

        yield from filter(
            None, map(self.track_info, self._search_api("recording", criteria))
        )

    def album_for_id(
        self, album_id: str
    ) -> beets.autotag.hooks.AlbumInfo | None:
        """Fetches an album by its MusicBrainz ID and returns an AlbumInfo
        object or None if the album is not found. May raise a
        MusicBrainzAPIError.
        """
        self._log.debug("Requesting MusicBrainz release {}", album_id)
        if not (albumid := self._extract_id(album_id)):
            self._log.debug("Invalid MBID ({}).", album_id)
            return None

        try:
            res = musicbrainzngs.get_release_by_id(albumid, RELEASE_INCLUDES)

            # resolve linked release relations
            actual_res = None

            if res["release"].get("status") == "Pseudo-Release":
                actual_res = _find_actual_release_from_pseudo_release(res)

        except musicbrainzngs.ResponseError:
            self._log.debug("Album ID match failed.")
            return None
        except musicbrainzngs.MusicBrainzError as exc:
            raise MusicBrainzAPIError(
                exc, "get release by ID", albumid, traceback.format_exc()
            )

        # release is potentially a pseudo release
        release = self.album_info(res["release"])

        # should be None unless we're dealing with a pseudo release
        if actual_res is not None:
            actual_release = self.album_info(actual_res["release"])
            return _merge_pseudo_and_actual_album(release, actual_release)
        else:
            return release

    def track_for_id(
        self, track_id: str
    ) -> beets.autotag.hooks.TrackInfo | None:
        """Fetches a track by its MusicBrainz ID. Returns a TrackInfo object
        or None if no track is found. May raise a MusicBrainzAPIError.
        """
        if not (trackid := self._extract_id(track_id)):
            self._log.debug("Invalid MBID ({}).", track_id)
            return None

        try:
            res = musicbrainzngs.get_recording_by_id(trackid, TRACK_INCLUDES)
        except musicbrainzngs.ResponseError:
            self._log.debug("Track ID match failed.")
            return None
        except musicbrainzngs.MusicBrainzError as exc:
            raise MusicBrainzAPIError(
                exc, "get recording by ID", trackid, traceback.format_exc()
            )
        return self.track_info(res["recording"])
