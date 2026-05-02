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

from beets import config, plugins, util
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.metadata_plugins import IDResponse, SearchApiMetadataSourcePlugin
from beets.util.deprecation import deprecate_for_user
from beets.util.id_extractors import extract_release_id

from ._utils.musicbrainz import MusicBrainzAPIMixin
from ._utils.requests import HTTPNotFoundError

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from beets.library import Item
    from beets.metadata_plugins import QueryType, SearchParams

    from ._utils.musicbrainz import (
        Alias,
        ArtistCredit,
        ArtistRelation,
        LabelInfo,
        Medium,
        Recording,
        Release,
        ReleaseGroup,
        UrlRelation,
        WorkRelation,
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


class WorkRelationsInfo(TypedDict):
    work: str | None
    mb_workid: str | None
    lyricists: list[str] | None
    lyricists_ids: list[str] | None
    composers: list[str] | None
    composers_ids: list[str] | None
    composer_sort: str | None


class ArtistRelationsInfo(TypedDict):
    arrangers: list[str] | None
    arrangers_ids: list[str] | None
    remixers: list[str] | None
    remixers_ids: list[str] | None


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


def _key_with_preferred_alias(
    obj: ReleaseGroup | Release | Recording, key: Literal["title"]
) -> str:
    alias = _preferred_alias(obj.get("aliases", []))
    return alias["name"] if alias else obj[key]


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

    Missing components are returned as `None`.
    """
    if not date_str:
        return None, None, None

    def _parse_part(part: str) -> int | None:
        try:
            return int(part)
        except ValueError:
            return None

    parts = list(map(_parse_part, date_str.split("-")))

    return (
        parts[0] if len(parts) > 0 else None,
        parts[1] if len(parts) > 1 else None,
        parts[2] if len(parts) > 2 else None,
    )


def _merge_pseudo_and_actual_album(
    pseudo: AlbumInfo, actual: AlbumInfo
) -> AlbumInfo:
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
            "genres",
        ]
    }
    merged.update(from_actual)
    return merged


class MusicBrainzPlugin(
    MusicBrainzAPIMixin, SearchApiMetadataSourcePlugin[IDResponse]
):
    @cached_property
    def genres_field(self) -> Literal["genres", "tags"]:
        choices: list[Literal["genre", "tag"]] = ["genre", "tag"]
        choice = self.config["genres_tag"].as_choice(choices)
        if choice == "genre":
            return "genres"
        return "tags"

    @cached_property
    def ignored_media(self) -> set[str]:
        return set(config["match"]["ignored_media"].as_str_seq())

    @cached_property
    def ignore_data_tracks(self) -> bool:
        return config["match"]["ignore_data_tracks"].get(bool)

    @cached_property
    def ignore_video_tracks(self) -> bool:
        return config["match"]["ignore_video_tracks"].get(bool)

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

        When available, a preferred alias is used for the canonical artist name,
        sort name and the credit name.
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
            credit_artist_object = alias or el

            joinphrase = el["joinphrase"]
            for name, parts, multi in (
                (artist_object["name"], artist_parts, artists),
                (artist_object["sort_name"], artist_sort_parts, artists_sort),
                (
                    credit_artist_object["name"],
                    artist_credit_parts,
                    artists_credit,
                ),
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

    @staticmethod
    def _parse_work_relations(
        relations: list[WorkRelation],
    ) -> WorkRelationsInfo:
        """Extract composer and lyricist credits from work relations.

        Traverses performance-type relations to collect associated artist
        credits, separating them into composers and lyricists along with
        their MusicBrainz IDs and sort names.
        """
        lyricists: list[str] = []
        lyricists_ids: list[str] = []
        composers: list[str] = []
        composers_ids: list[str] = []
        composer_sort: list[str] = []

        artist_relations = [
            ar
            for r in relations
            if r["type"] == "performance"
            for ar in r["work"].get("artist_relations", [])
        ]
        for artist_relation in artist_relations:
            rel_type = artist_relation["type"]
            if rel_type == "lyricist":
                lyricists.append(artist_relation["artist"]["name"])
                lyricists_ids.append(artist_relation["artist"]["id"])
            elif rel_type == "composer":
                composers.append(artist_relation["artist"]["name"])
                composers_ids.append(artist_relation["artist"]["id"])
                composer_sort.append(artist_relation["artist"]["sort_name"])

        return {
            # TODO: double-check if we should really use the last work here
            "work": relations[-1]["work"]["title"] if relations else None,
            "mb_workid": relations[-1]["work"]["id"] if relations else None,
            "lyricists": lyricists or None,
            "lyricists_ids": lyricists_ids or None,
            "composers": composers or None,
            "composers_ids": composers_ids or None,
            "composer_sort": ", ".join(composer_sort) or None,
        }

    @staticmethod
    def _parse_artist_relations(
        relations: list[ArtistRelation],
    ) -> ArtistRelationsInfo:
        """Extract arranger and remixer credits from artist relations.

        Traverses recording-level artist relations to collect associated artist
        credits, separating them into arrangers and remixers along with their
        MusicBrainz IDs.
        """
        arrangers: list[str] = []
        arrangers_ids: list[str] = []
        remixers: list[str] = []
        remixers_ids: list[str] = []

        for artist_relation in relations:
            rel_type = artist_relation["type"]
            if rel_type == "arranger":
                arrangers.append(artist_relation["artist"]["name"])
                arrangers_ids.append(artist_relation["artist"]["id"])
            elif rel_type == "remixer":
                remixers.append(artist_relation["artist"]["name"])
                remixers_ids.append(artist_relation["artist"]["id"])

        return {
            "arrangers": arrangers or None,
            "arrangers_ids": arrangers_ids or None,
            "remixers": remixers or None,
            "remixers_ids": remixers_ids or None,
        }

    def track_info(self, recording: Recording) -> TrackInfo:
        """Build a `TrackInfo` object from a MusicBrainz recording payload.

        This is the main translation layer between MusicBrainz's recording model
        and beets' internal autotag representation. It gathers core identifying
        metadata (title, MBIDs, URLs), timing information, and artist-credit
        fields, then enriches the result with relationship-derived roles (such
        as remixers and arrangers) and work-level credits (such as lyricists and
        composers).
        """
        title = _key_with_preferred_alias(recording, key="title")

        info = TrackInfo(
            title=title,
            track_id=recording["id"],
            data_source=self.data_source,
            data_url=urljoin(BASE_URL, f"recording/{recording['id']}"),
            length=(
                length / 1000.0 if (length := recording["length"]) else None
            ),
            trackdisambig=recording["disambiguation"] or None,
            isrc=(
                ";".join(isrcs) if (isrcs := recording.get("isrcs")) else None
            ),
            **self._parse_artist_credits(recording["artist_credit"]),
            **self._parse_work_relations(recording.get("work_relations", [])),
            **self._parse_artist_relations(
                recording.get("artist_relations", [])
            ),
        )

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
            release_group_title=_key_with_preferred_alias(
                release_group, key="title"
            ),
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
            if (_label := label_info["label"]) and (
                label_name := _label["name"]
            ) != "[no label]":
                label = label_name

        return {"label": label, "catalognum": catalognum}

    def _parse_genres(self, release: Release) -> list[str] | None:
        if self.config["genres"] and (
            genres := [
                *release["release_group"][self.genres_field],
                *release[self.genres_field],
            ]
        ):
            count_by_genre: dict[str, int] = defaultdict(int)
            for genre in genres:
                count_by_genre[genre["name"]] += genre["count"]

            return [
                g
                for g, _ in sorted(count_by_genre.items(), key=lambda g: -g[1])
            ]

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

    def get_tracks_from_medium(self, medium: Medium) -> Iterable[TrackInfo]:
        all_tracks = []
        if pregap := medium.get("pregap"):
            all_tracks.append(pregap)

        all_tracks.extend(medium.get("tracks", []))

        if not self.ignore_data_tracks:
            all_tracks.extend(medium.get("data_tracks", []))

        medium_data = {
            "medium": medium["position"],
            "medium_total": medium["track_count"],
            "disctitle": medium["title"],
            "media": medium["format"],
        }
        valid_tracks = [
            t
            for t in all_tracks
            if (
                # skip data tracks without titles
                t["recording"]["title"] != "[data track]"
                # and video tracks if we're configured to ignore them
                and not (self.ignore_video_tracks and t["recording"]["video"])
            )
        ]
        for track in valid_tracks:
            # make a copy since we need to modify it with track-level overrides
            recording = track["recording"].copy()
            # Prefer track data, where present, over recording data.
            recording["length"] = track["length"] or recording["length"]
            recording["artist_credit"] = (
                track["artist_credit"] or recording["artist_credit"]
            )
            if track["title"] and not _preferred_alias(recording["aliases"]):
                recording["title"] = track["title"]

            ti = self.track_info(recording)
            ti.update(
                medium_index=int(track["position"]),
                release_track_id=track["id"],
                track_alt=track["number"],
                **medium_data,
            )

            yield ti

    def _ensure_complete_recordings(self, release: Release) -> None:
        """Patch a release's tracks with full recording data from the API.

        The MusicBrainz API silently omits relation data for releases
        exceeding a track threshold. This method detects that case and
        re-fetches recordings in paginated chunks, then mutates the
        release in-place so callers always see complete data.
        """
        track_count = sum(len(m.get("tracks", [])) for m in release["media"])
        if track_count > BROWSE_MAXTRACKS:
            self._log.debug("Album {} has too many tracks", release["id"])
            recordings: list[Recording] = []
            for i in range(0, track_count, BROWSE_CHUNKSIZE):
                self._log.debug("Retrieving tracks starting at {}", i)
                recordings.extend(
                    self.mb_api.browse_recordings(
                        release=release["id"],
                        limit=BROWSE_CHUNKSIZE,
                        includes=BROWSE_INCLUDES,
                        offset=i,
                    )
                )
            recording_by_id = {r["id"]: r for r in recordings}
            for medium in release["media"]:
                for track in medium["tracks"]:
                    track["recording"] = recording_by_id[
                        track["recording"]["id"]
                    ]

    def album_info(self, release: Release) -> AlbumInfo:
        """Takes a MusicBrainz release result dictionary and returns a beets
        AlbumInfo object containing the interesting data about that release.
        """
        self._ensure_complete_recordings(release)

        # Basic info.
        valid_media = [
            m for m in release["media"] if m["format"] not in self.ignored_media
        ]
        track_infos: list[TrackInfo] = []
        for medium in valid_media:
            track_infos.extend(self.get_tracks_from_medium(medium))

        for index, track_info in enumerate(track_infos, 1):
            track_info.index = index

        release_title = _key_with_preferred_alias(release, key="title")
        info = AlbumInfo(
            **self._parse_artist_credits(release["artist_credit"]),
            album=release_title,
            album_id=release["id"],
            tracks=track_infos,
            media=(
                medias.pop()
                if len(medias := {t.media for t in track_infos}) == 1
                else "Media"
            ),
            mediums=len(release["media"]),
            data_source=self.data_source,
            data_url=urljoin(BASE_URL, f"release/{release['id']}"),
            barcode=release.get("barcode"),
            genres=self._parse_genres(release),
            script=release["text_representation"]["script"],
            language=release["text_representation"]["language"],
            asin=release["asin"],
            albumstatus=release["status"],
            albumdisambig=release["disambiguation"] or None,
            **self._parse_release_group(release["release_group"]),
            **self._parse_label_infos(release["label_info"]),
            **self._parse_external_ids(release.get("url_relations", [])),
        )
        info.va = info.artist_id == VARIOUS_ARTISTS_ID
        if info.va:
            va_name = config["va_name"].as_str()
            info.artist = va_name
            info.artist_sort = va_name
            info.artists = [va_name]
            info.artists_sort = [va_name]
            info.artist_credit = va_name
            info.artists_credit = [va_name]

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

    def get_search_query_with_filters(
        self,
        query_type: QueryType,
        items: Sequence[Item],
        artist: str,
        name: str,
        va_likely: bool,
    ) -> tuple[str, dict[str, str]]:
        """Build MusicBrainz criteria filters for album and recording search."""

        if query_type == "album":
            criteria = self.get_album_criteria(items, artist, name, va_likely)
        else:
            criteria = {"artist": artist, "recording": name, "alias": name}

        return "", {
            k: _v for k, v in criteria.items() if (_v := v.lower().strip())
        }

    def get_search_response(self, params: SearchParams) -> Sequence[IDResponse]:
        """Search MusicBrainz and return release or recording result mappings."""

        mb_entity: Literal["release", "recording"] = (
            "release" if params.query_type == "album" else "recording"
        )
        return self.mb_api.search(
            mb_entity, dict(params.filters), limit=params.limit
        )

    def album_for_id(self, album_id: str) -> AlbumInfo | None:
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
            original_release = self.mb_api.get_release(albumid)
        except HTTPNotFoundError:
            self._log.debug("Release {} not found on MusicBrainz.", albumid)
            return None

        album = self.album_info(original_release)

        if original_release["status"] == "Pseudo-Release":
            linked_releases = (
                rel
                for rel in original_release.get("release_relations", [])
                if (
                    rel["type"] == "transl-tracklisting"
                    and rel["direction"] == "backward"
                )
            )
            if rel := next(linked_releases, None):
                actual_release = self.mb_api.get_release(rel["release"]["id"])
                album = _merge_pseudo_and_actual_album(
                    album, self.album_info(actual_release)
                )

        return album

    def track_for_id(self, track_id: str) -> TrackInfo | None:
        """Fetches a track by its MusicBrainz ID. Returns a TrackInfo object
        or None if no track is found. May raise a MusicBrainzAPIError.
        """
        if not (trackid := self._extract_id(track_id)):
            self._log.debug("Invalid MBID ({}).", track_id)
            return None

        with suppress(HTTPNotFoundError):
            return self.track_info(self.mb_api.get_recording(trackid))

        return None
