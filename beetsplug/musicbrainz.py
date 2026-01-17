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

from collections import Counter
from contextlib import suppress
from functools import cached_property
from itertools import product
from typing import TYPE_CHECKING, Literal
from urllib.parse import urljoin

from confuse.exceptions import NotFoundError

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
        Recording,
        Release,
    )

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


def _preferred_alias(
    aliases: list[Alias], languages: list[str] | None = None
) -> Alias | None:
    """Given a list of alias structures for an artist credit, select
    and return the user's preferred alias or None if no matching
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
                and alias.get("primary")
                and (alias.get("type") or "").lower() not in ignored_alias_types
            ):
                matches.append(alias)

        # Skip to the next locale if we have no matches
        if not matches:
            continue

        return matches[0]

    return None


def _multi_artist_credit(
    credit: list[ArtistCredit], include_join_phrase: bool
) -> tuple[list[str], list[str], list[str]]:
    """Given a list representing an ``artist-credit`` block, accumulate
    data into a triple of joined artist name lists: canonical, sort, and
    credit.
    """
    artist_parts = []
    artist_sort_parts = []
    artist_credit_parts = []
    for el in credit:
        alias = _preferred_alias(el["artist"].get("aliases", []))

        # An artist.
        if alias:
            cur_artist_name = alias["name"]
        else:
            cur_artist_name = el["artist"]["name"]
        artist_parts.append(cur_artist_name)

        # Artist sort name.
        if alias:
            artist_sort_parts.append(alias["sort_name"])
        elif "sort_name" in el["artist"]:
            artist_sort_parts.append(el["artist"]["sort_name"])
        else:
            artist_sort_parts.append(cur_artist_name)

        # Artist credit.
        if "name" in el:
            artist_credit_parts.append(el["name"])
        else:
            artist_credit_parts.append(cur_artist_name)

        if include_join_phrase and (joinphrase := el.get("joinphrase")):
            artist_parts.append(joinphrase)
            artist_sort_parts.append(joinphrase)
            artist_credit_parts.append(joinphrase)

    return (
        artist_parts,
        artist_sort_parts,
        artist_credit_parts,
    )


def track_url(trackid: str) -> str:
    return urljoin(BASE_URL, f"recording/{trackid}")


def _flatten_artist_credit(credit: list[ArtistCredit]) -> tuple[str, str, str]:
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


def _artist_ids(credit: list[ArtistCredit]) -> list[str]:
    """
    Given a list representing an ``artist-credit``,
    return a list of artist IDs
    """
    artist_ids: list[str] = []
    for el in credit:
        if isinstance(el, dict):
            artist_ids.append(el["artist"]["id"])

    return artist_ids


def _get_related_artist_names(
    relations: list[ArtistRelation], relation_type: ArtistRelationType
) -> str:
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


def _preferred_release_event(release: Release) -> tuple[str | None, str | None]:
    """Given a release, select and return the user's preferred release
    event as a tuple of (country, release_date). Fall back to the
    default release event if a preferred event is not found.
    """
    preferred_countries: Sequence[str] = config["match"]["preferred"][
        "countries"
    ].as_str_seq()

    for country in preferred_countries:
        for event in release.get("release_events", {}):
            try:
                if area := event.get("area"):
                    if country in area["iso_3166_1_codes"]:
                        return country, event["date"]
            except KeyError:
                pass

    return release.get("country"), release.get("date")


def _set_date_str(
    info: beets.autotag.hooks.AlbumInfo,
    date_str: str,
    original: bool = False,
) -> None:
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

    def track_info(
        self,
        recording: Recording,
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

        if recording.get("artist_credit"):
            # Get the artist names.
            (
                info.artist,
                info.artist_sort,
                info.artist_credit,
            ) = _flatten_artist_credit(recording["artist_credit"])

            (
                info.artists,
                info.artists_sort,
                info.artists_credit,
            ) = _multi_artist_credit(
                recording["artist_credit"], include_join_phrase=False
            )

            info.artists_ids = _artist_ids(recording["artist_credit"])
            info.artist_id = info.artists_ids[0]

        if recording.get("artist_relations"):
            info.remixer = _get_related_artist_names(
                recording["artist_relations"], relation_type="remixer"
            )

        if length := recording["length"]:
            info.length = int(length) / 1000.0

        info.trackdisambig = recording["disambiguation"] or None

        if recording.get("isrcs"):
            info.isrc = ";".join(recording["isrcs"])

        lyricist = []
        composer = []
        composer_sort = []
        for work_relation in recording.get("work_relations", ()):
            if work_relation["type"] != "performance":
                continue
            info.work = work_relation["work"]["title"]
            info.mb_workid = work_relation["work"]["id"]
            if "disambiguation" in work_relation["work"]:
                info.work_disambig = work_relation["work"]["disambiguation"]

            for artist_relation in work_relation["work"].get(
                "artist_relations", ()
            ):
                if "type" in artist_relation:
                    type = artist_relation["type"]
                    if type == "lyricist":
                        lyricist.append(artist_relation["artist"]["name"])
                    elif type == "composer":
                        composer.append(artist_relation["artist"]["name"])
                        composer_sort.append(
                            artist_relation["artist"]["sort_name"]
                        )
        if lyricist:
            info.lyricist = ", ".join(lyricist)
        if composer:
            info.composer = ", ".join(composer)
            info.composer_sort = ", ".join(composer_sort)

        arranger = []
        for artist_relation in recording.get("artist_relations", ()):
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

    def album_info(self, release: Release) -> beets.autotag.hooks.AlbumInfo:
        """Takes a MusicBrainz release result dictionary and returns a beets
        AlbumInfo object containing the interesting data about that release.
        """
        # Get artist name using join phrases.
        artist_name, artist_sort_name, artist_credit_name = (
            _flatten_artist_credit(release["artist_credit"])
        )

        (
            artists_names,
            artists_sort_names,
            artists_credit_names,
        ) = _multi_artist_credit(
            release["artist_credit"], include_join_phrase=False
        )

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
                if (
                    "title" in track["recording"]
                    and track["recording"]["title"] in SKIPPED_TRACKS
                ):
                    continue

                if (
                    "video" in track["recording"]
                    and track["recording"]["video"]
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
                    # Get the artist names.
                    (
                        ti.artist,
                        ti.artist_sort,
                        ti.artist_credit,
                    ) = _flatten_artist_credit(track["artist_credit"])

                    (
                        ti.artists,
                        ti.artists_sort,
                        ti.artists_credit,
                    ) = _multi_artist_credit(
                        track["artist_credit"], include_join_phrase=False
                    )

                    ti.artists_ids = _artist_ids(track["artist_credit"])
                    ti.artist_id = ti.artists_ids[0]
                if track.get("length"):
                    ti.length = int(track["length"]) / (1000.0)

                track_infos.append(ti)

        album_artist_ids = _artist_ids(release["artist_credit"])
        info = beets.autotag.hooks.AlbumInfo(
            album=release["title"],
            album_id=release["id"],
            artist=artist_name,
            artist_id=album_artist_ids[0],
            artists=artists_names,
            artists_ids=album_artist_ids,
            tracks=track_infos,
            mediums=len(release["media"]),
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
        info.releasegroup_id = release["release_group"]["id"]
        info.albumstatus = release.get("status")

        if release["release_group"].get("title"):
            info.release_group_title = release["release_group"].get("title")

        # Get the disambiguation strings at the release and release group level.
        if release["release_group"].get("disambiguation"):
            info.releasegroupdisambig = release["release_group"].get(
                "disambiguation"
            )
        if release.get("disambiguation"):
            info.albumdisambig = release.get("disambiguation")

        if reltype := release["release_group"].get("primary_type"):
            info.albumtype = reltype.lower()

        # Set the new-style "primary" and "secondary" release types.
        albumtypes = []
        if "primary_type" in release["release_group"]:
            rel_primarytype = release["release_group"]["primary_type"]
            if rel_primarytype:
                albumtypes.append(rel_primarytype.lower())
        if "secondary_types" in release["release_group"]:
            if release["release_group"]["secondary_types"]:
                for sec_type in release["release_group"]["secondary_types"]:
                    albumtypes.append(sec_type.lower())
        info.albumtypes = albumtypes

        # Release events.
        info.country, release_date = _preferred_release_event(release)
        release_group_date = release["release_group"].get("first_release_date")
        if not release_date:
            # Fall back if release-specific date is not available.
            release_date = release_group_date

        if release_date:
            _set_date_str(info, release_date, False)
        _set_date_str(info, release_group_date, True)

        # Label name.
        if release.get("label_info"):
            label_info = release["label_info"][0]
            if label_info.get("label"):
                label = label_info["label"]["name"]
                if label != "[no label]":
                    info.label = label
            info.catalognum = label_info.get("catalog_number")

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

        if self.config["genres"]:
            sources = [
                release["release_group"].get(self.genres_field, []),
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
        wanted_sources: set[UrlSource] = {
            site for site, wanted in external_ids.items() if wanted
        }
        if wanted_sources and (url_rels := release.get("url_relations")):
            urls = {}

            for url_source, url_relation in product(wanted_sources, url_rels):
                if f"{url_source}.com" in (
                    target := url_relation["url"]["resource"]
                ):
                    urls[url_source] = target
                    self._log.debug(
                        "Found link to {} release via MusicBrainz",
                        url_source.capitalize(),
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
