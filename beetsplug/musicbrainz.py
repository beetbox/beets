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

from collections import defaultdict
from contextlib import suppress
from functools import cached_property
from itertools import product
from typing import TYPE_CHECKING, Literal, TypedDict
from urllib.parse import urljoin

from confuse.exceptions import NotFoundError
from typing_extensions import NotRequired

import beets
import beets.autotag.hooks
from beets import config, plugins, util
from beets.metadata_plugins import MetadataSourcePlugin
from beets.util.deprecation import deprecate_for_user
from beets.util.id_extractors import extract_release_id

from ._utils.musicbrainz import MusicBrainzAPIMixin
from ._utils.requests import HTTPNotFoundError

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from beets.library import Item

    from ._typing import JSONDict
    from ._utils.musicbrainz import (
        Alias,
        ArtistCredit,
        ArtistRelation,
        ArtistRelationType,
        LabelInfo,
        Recording,
        Release,
        ReleaseGroup,
        UrlRelation,
    )

VARIOUS_ARTISTS_ID = "89ad4ac3-39f7-470e-963a-56509c546377"

BASE_URL = "https://musicbrainz.org/"

FIELDS_TO_MB_KEYS = {
    "barcode": "barcode",
    "catalognum": "catno",
    "country": "country",
    "label": "label",
    "media": "format",
    "year": "date",
    "tracks": "tracks",
    "alias": "alias",
}

BROWSE_INCLUDES = [
    "artist-credits",
    "work-rels",
    "artist-rels",
    "recording-rels",
    "release-rels",
]
BROWSE_CHUNKSIZE = 100
BROWSE_MAXTRACKS = 500


UrlSource = Literal[
    "discogs", "bandcamp", "spotify", "deezer", "tidal", "beatport"
]


class ArtistInfo(TypedDict):
    artist: str
    artist_id: str
    artist_sort: str
    artist_credit: str
    artists: list[str]
    artists_ids: list[str]
    artists_sort: list[str]
    artists_credit: list[str]


class ReleaseGroupInfo(TypedDict):
    albumtype: str | None
    albumtypes: list[str]
    releasegroup_id: str
    release_group_title: str | None
    releasegroupdisambig: str | None
    original_year: int | None
    original_month: int | None
    original_day: int | None


class LabelInfoInfo(TypedDict):
    label: str | None
    catalognum: str | None


class ExternalIdsInfo(TypedDict):
    discogs_album_id: NotRequired[str | None]
    bandcamp_album_id: NotRequired[str | None]
    spotify_album_id: NotRequired[str | None]
    deezer_album_id: NotRequired[str | None]
    tidal_album_id: NotRequired[str | None]
    beatport_album_id: NotRequired[str | None]


def _preferred_alias(
    aliases: list[Alias], languages: list[str] | None = None
) -> Alias | None:
    """Select the most appropriate alias based on user preferences."""
    if not aliases:
        return None

    # Get any ignored alias types and lower case them to prevent case issues
    ignored_alias_types = {
        a.lower() for a in config["import"]["ignored_alias_types"].as_str_seq()
    }

    # Search configured locales in order.
    languages = languages or config["import"]["languages"].as_str_seq()

    matches = (
        al
        for locale in languages
        for al in aliases
        # Find matching primary aliases for this locale that are not
        # being ignored
        if (
            al["locale"] == locale
            and al["primary"]
            and (al["type"] or "").lower() not in ignored_alias_types
        )
    )
    return next(matches, None)


def _get_related_artist_names(
    relations: list[ArtistRelation], relation_type: ArtistRelationType
) -> str:
    """Return a comma-separated list of artist names for a relation type."""
    return ", ".join(
        r["artist"]["name"] for r in relations if r["type"] == relation_type
    )


def _preferred_release_event(release: Release) -> tuple[str | None, str | None]:
    """Select the most relevant release country and date for matching.

    Fall back to the default release event if a preferred event is not found.
    """
    preferred_countries = config["match"]["preferred"]["countries"].as_str_seq()

    for country in preferred_countries:
        for event in release.get("release_events", []):
            if (area := event["area"]) and country in area["iso_3166_1_codes"]:
                return country, event["date"]

    return release.get("country"), release.get("date")


def _get_date(date_str: str) -> tuple[int | None, int | None, int | None]:
    """Parse a partial `YYYY-MM-DD` string into numeric date parts.

    Missing components are returned as `None`. Invalid components are ignored.
    """
    if not date_str:
        return None, None, None

    parts = list(map(int, date_str.split("-")))

    return (
        parts[0] if len(parts) > 0 else None,
        parts[1] if len(parts) > 1 else None,
        parts[2] if len(parts) > 2 else None,
    )


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


class MusicBrainzPlugin(MusicBrainzAPIMixin, MetadataSourcePlugin):
    @cached_property
    def genres_field(self) -> Literal["genres", "tags"]:
        choices: list[Literal["genre", "tag"]] = ["genre", "tag"]
        choice = self.config["genres_tag"].as_choice(choices)
        if choice == "genre":
            return "genres"
        return "tags"

    def __init__(self) -> None:
        """Set up the python-musicbrainz-ngs module according to settings
        from the beets configuration. This should be called at startup.
        """
        super().__init__()
        self.config.add(
            {
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
            deprecate_for_user(
                self._log,
                "'musicbrainz.searchlimit' configuration option",
                "'musicbrainz.search_limit'",
            )

    @staticmethod
    def _parse_artist_credits(artist_credits: list[ArtistCredit]) -> ArtistInfo:
        """Normalize MusicBrainz artist-credit data into tag-friendly fields.

        MusicBrainz represents credits as a sequence of credited artists, each
        with a display name and a `joinphrase` (for example `' & '`, `' feat.
        '`, or `''`). This helper converts that structured representation into
        both:

        - Single string values suitable for common tags (concatenated names with
          joinphrases preserved).
        - Parallel lists that keep the per-artist granularity for callers that
          need to reason about individual credited artists.

        When available, a preferred alias is used for the canonical artist name
        and sort name, while the credit name preserves the exact credited text
        from the release.
        """
        artist_parts: list[str] = []
        artist_sort_parts: list[str] = []
        artist_credit_parts: list[str] = []
        artists: list[str] = []
        artists_sort: list[str] = []
        artists_credit: list[str] = []
        artists_ids: list[str] = []

        for el in artist_credits:
            artists_ids.append(el["artist"]["id"])
            alias = _preferred_alias(el["artist"].get("aliases", []))
            artist_object = alias or el["artist"]

            joinphrase = el["joinphrase"]
            for name, parts, multi in (
                (artist_object["name"], artist_parts, artists),
                (artist_object["sort_name"], artist_sort_parts, artists_sort),
                (el["name"], artist_credit_parts, artists_credit),
            ):
                parts.extend([name, joinphrase])
                multi.append(name)

        return {
            "artist": "".join(artist_parts),
            "artist_id": artists_ids[0],
            "artist_sort": "".join(artist_sort_parts),
            "artist_credit": "".join(artist_credit_parts),
            "artists": artists,
            "artists_ids": artists_ids,
            "artists_sort": artists_sort,
            "artists_credit": artists_credit,
        }

    def track_info(
        self,
        recording: Recording,
        index: int | None = None,
        medium: int | None = None,
        medium_index: int | None = None,
        medium_total: int | None = None,
    ) -> beets.autotag.hooks.TrackInfo:
        """Build a `TrackInfo` object from a MusicBrainz recording payload.

        This is the main translation layer between MusicBrainz's recording model
        and beets' internal autotag representation. It gathers core identifying
        metadata (title, MBIDs, URLs), timing information, and artist-credit
        fields, then enriches the result with relationship-derived roles (such
        as remixers and arrangers) and work-level credits (such as lyricists and
        composers).
        """
        info = beets.autotag.hooks.TrackInfo(
            title=recording["title"],
            track_id=recording["id"],
            index=index,
            medium=medium,
            medium_index=medium_index,
            medium_total=medium_total,
            data_source=self.data_source,
            data_url=urljoin(BASE_URL, f"recording/{recording['id']}"),
            length=(
                int(length) / 1000.0
                if (length := recording["length"])
                else None
            ),
            trackdisambig=recording["disambiguation"] or None,
            isrc=(
                ";".join(isrcs) if (isrcs := recording.get("isrcs")) else None
            ),
            **self._parse_artist_credits(recording["artist_credit"]),
        )

        if artist_relations := recording.get("artist_relations"):
            if remixer := _get_related_artist_names(
                artist_relations, "remixer"
            ):
                info.remixer = remixer
            if arranger := _get_related_artist_names(
                artist_relations, "arranger"
            ):
                info.arranger = arranger

        lyricist: list[str] = []
        composer: list[str] = []
        composer_sort: list[str] = []
        for work_relation in recording.get("work_relations", ()):
            if work_relation["type"] != "performance":
                continue

            work = work_relation["work"]
            info.work = work["title"]
            info.mb_workid = work["id"]
            if "disambiguation" in work:
                info.work_disambig = work["disambiguation"]

            for artist_relation in work.get("artist_relations", ()):
                if (rel_type := artist_relation["type"]) == "lyricist":
                    lyricist.append(artist_relation["artist"]["name"])
                elif rel_type == "composer":
                    composer.append(artist_relation["artist"]["name"])
                    composer_sort.append(artist_relation["artist"]["sort_name"])
        if lyricist:
            info.lyricist = ", ".join(lyricist)
        if composer:
            info.composer = ", ".join(composer)
            info.composer_sort = ", ".join(composer_sort)

        # Supplementary fields provided by plugins
        extra_trackdatas = plugins.send("mb_track_extract", data=recording)
        for extra_trackdata in extra_trackdatas:
            info.update(extra_trackdata)

        return info

    @staticmethod
    def _parse_release_group(release_group: ReleaseGroup) -> ReleaseGroupInfo:
        albumtype = None
        albumtypes = []
        if reltype := release_group["primary_type"]:
            albumtype = reltype.lower()
            albumtypes.append(albumtype)

        year, month, day = _get_date(release_group["first_release_date"])
        return ReleaseGroupInfo(
            albumtype=albumtype,
            albumtypes=[
                *albumtypes,
                *(st.lower() for st in release_group["secondary_types"]),
            ],
            releasegroup_id=release_group["id"],
            release_group_title=release_group["title"],
            releasegroupdisambig=release_group["disambiguation"] or None,
            original_year=year,
            original_month=month,
            original_day=day,
        )

    @staticmethod
    def _parse_label_infos(label_infos: list[LabelInfo]) -> LabelInfoInfo:
        catalognum = label = None
        if label_infos:
            label_info = label_infos[0]
            catalognum = label_info["catalog_number"]
            if (_label := label_info["label"]["name"]) != "[no label]":
                label = _label

        return {"label": label, "catalognum": catalognum}

    def _parse_genre(self, release: Release) -> str | None:
        if self.config["genres"]:
            genres = [
                *release["release_group"][self.genres_field],
                *release.get(self.genres_field, []),
            ]
            count_by_genre: dict[str, int] = defaultdict(int)
            for genre in genres:
                count_by_genre[genre["name"]] += int(genre["count"])

            return "; ".join(
                g
                for g, _ in sorted(count_by_genre.items(), key=lambda g: -g[1])
            )

        return None

    def _parse_external_ids(
        self, url_relations: list[UrlRelation]
    ) -> ExternalIdsInfo:
        """Extract configured external release ids from MusicBrainz URLs.

        MusicBrainz releases can include `url_relations` pointing to third-party
        sites (for example Bandcamp or Discogs). This helper filters those URL
        relations to only the sources enabled in configuration, then derives a
        stable external identifier from each matching URL.
        """
        external_ids = self.config["external_ids"].get()
        wanted_sources: set[UrlSource] = {
            site for site, wanted in external_ids.items() if wanted
        }
        url_by_source: dict[UrlSource, str] = {}
        for source, url_relation in product(wanted_sources, url_relations):
            if f"{source}.com" in (target := url_relation["url"]["resource"]):
                url_by_source[source] = target
                self._log.debug(
                    "Found link to {} release via MusicBrainz",
                    source.capitalize(),
                )

        return {
            f"{source}_album_id": extract_release_id(source, url)
            for source, url in url_by_source.items()
        }  # type: ignore[return-value]

    def album_info(self, release: Release) -> beets.autotag.hooks.AlbumInfo:
        """Takes a MusicBrainz release result dictionary and returns a beets
        AlbumInfo object containing the interesting data about that release.
        """
        ntracks = sum(len(m.get("tracks", [])) for m in release["media"])

        # The MusicBrainz API omits 'relations'
        # when the release has more than 500 tracks. So we use browse_recordings
        # on chunks of tracks to recover the same information in this case.
        if ntracks > BROWSE_MAXTRACKS:
            self._log.debug("Album {} has too many tracks", release["id"])
            recording_list: list[Recording] = []
            for i in range(0, ntracks, BROWSE_CHUNKSIZE):
                self._log.debug("Retrieving tracks starting at {}", i)
                recording_list.extend(
                    self.mb_api.browse_recordings(
                        release=release["id"],
                        limit=BROWSE_CHUNKSIZE,
                        includes=BROWSE_INCLUDES,
                        offset=i,
                    )
                )
            recording_by_id = {r["id"]: r for r in recording_list}
            for medium in release["media"]:
                for track in medium["tracks"]:
                    track["recording"] = recording_by_id[
                        track["recording"]["id"]
                    ]

        # Basic info.
        track_infos = []
        index = 0
        for medium in release["media"]:
            disctitle = medium.get("title")
            format = medium.get("format")

            if format in config["match"]["ignored_media"].as_str_seq():
                continue

            all_tracks = medium.get("tracks", [])
            if (
                "data_tracks" in medium
                and not config["match"]["ignore_data_tracks"]
            ):
                all_tracks += medium["data_tracks"]
            track_count = len(all_tracks)

            if "pregap" in medium:
                all_tracks.insert(0, medium["pregap"])

            for track in all_tracks:
                if track["recording"]["title"] == "[data track]" or (
                    track["recording"]["video"]
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
                if track.get("artist_credit"):
                    ti.update(
                        **self._parse_artist_credits(track["artist_credit"])
                    )
                if track.get("length"):
                    ti.length = int(track["length"]) / (1000.0)

                track_infos.append(ti)

        info = beets.autotag.hooks.AlbumInfo(
            **self._parse_artist_credits(release["artist_credit"]),
            album=release["title"],
            album_id=release["id"],
            tracks=track_infos,
            mediums=len(release["media"]),
            data_source=self.data_source,
            data_url=urljoin(BASE_URL, f"release/{release['id']}"),
            barcode=release.get("barcode"),
            genre=genre if (genre := self._parse_genre(release)) else None,
            **self._parse_release_group(release["release_group"]),
            **self._parse_label_infos(release["label_info"]),
            **self._parse_external_ids(release.get("url_relations", [])),
        )
        info.va = info.artist_id == VARIOUS_ARTISTS_ID
        if info.va:
            info.artist = config["va_name"].as_str()
        info.asin = release.get("asin")
        info.albumstatus = release.get("status")

        if release.get("disambiguation"):
            info.albumdisambig = release.get("disambiguation")

        # Release events.
        info.country, release_date = _preferred_release_event(release)
        info.year, info.month, info.day = (
            _get_date(release_date)
            if release_date
            else (
                info.original_year,
                info.original_month,
                info.original_day,
            )
        )

        # Text representation data.
        if release.get("text_representation"):
            rep = release["text_representation"]
            info.script = rep.get("script")
            info.language = rep.get("language")

        # Media (format).
        if release["media"]:
            # If all media are the same, use that medium name
            if len({m.get("format") for m in release["media"]}) == 1:
                info.media = release["media"][0].get("format")
            # Otherwise, let's just call it "Media"
            else:
                info.media = "Media"

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
        criteria = {"release": album} | (
            {"arid": VARIOUS_ARTISTS_ID} if va_likely else {"artist": artist}
        )

        for tag, mb_field in self.extra_mb_field_by_tag.items():
            if tag == "tracks":
                value = str(len(items))
            elif tag == "alias":
                value = album
            else:
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
        return self.mb_api.search(
            query_type, filters, limit=self.config["search_limit"].get()
        )

    def candidates(
        self,
        items: Sequence[Item],
        artist: str,
        album: str,
        va_likely: bool,
    ) -> Iterable[beets.autotag.hooks.AlbumInfo]:
        criteria = self.get_album_criteria(items, artist, album, va_likely)
        release_ids = (r["id"] for r in self._search_api("release", criteria))

        for id_ in release_ids:
            with suppress(HTTPNotFoundError):
                if album_info := self.album_for_id(id_):
                    yield album_info

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterable[beets.autotag.hooks.TrackInfo]:
        criteria = {"artist": artist, "recording": title, "alias": title}
        ids = (r["id"] for r in self._search_api("recording", criteria))

        return filter(None, map(self.track_for_id, ids))

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

        # A 404 error here is fine. e.g. re-importing a release that has
        # been deleted on MusicBrainz.
        try:
            res = self.mb_api.get_release(albumid)
        except HTTPNotFoundError:
            self._log.debug("Release {} not found on MusicBrainz.", albumid)
            return None

        # resolve linked release relations
        actual_res = None

        if res.get("status") == "Pseudo-Release" and (
            relations := res.get("release_relations")
        ):
            for rel in relations:
                if (
                    rel["type"] == "transl-tracklisting"
                    and rel["direction"] == "backward"
                ):
                    actual_res = self.mb_api.get_release(rel["release"]["id"])

        # release is potentially a pseudo release
        release = self.album_info(res)

        # should be None unless we're dealing with a pseudo release
        if actual_res is not None:
            actual_release = self.album_info(actual_res)
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

        with suppress(HTTPNotFoundError):
            return self.track_info(self.mb_api.get_recording(trackid))

        return None
