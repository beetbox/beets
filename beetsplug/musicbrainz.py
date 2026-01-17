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
from copy import deepcopy
from functools import cached_property
from itertools import chain, product
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import mediafile
from confuse.exceptions import NotFoundError

import beets
import beets.autotag.hooks
from beets import config, plugins, util
from beets.autotag.distance import distance
from beets.autotag.hooks import AlbumInfo
from beets.autotag.match import assign_items
from beets.metadata_plugins import MetadataSourcePlugin
from beets.util.deprecation import deprecate_for_user
from beets.util.id_extractors import extract_release_id

from ._utils.musicbrainz import MusicBrainzAPIMixin
from ._utils.requests import HTTPNotFoundError

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from typing import Literal

    from beets.autotag import AlbumMatch
    from beets.autotag.distance import Distance
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

_STATUS_PSEUDO = "Pseudo-Release"


def _preferred_alias(
    aliases: list[JSONDict], languages: list[str] | None = None
) -> JSONDict | None:
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
        alias = _preferred_alias(el["artist"].get("aliases", ()))

        # An artist.
        if alias:
            cur_artist_name = alias["name"]
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
        for event in release.get("release-events", {}):
            try:
                if area := event.get("area"):
                    if country in area["iso-3166-1-codes"]:
                        return country, event["date"]
            except KeyError:
                pass

    return release.get("country"), release.get("date")


def _set_date_str(
    info: AlbumInfo,
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
            "genre",
        ]
    }
    merged.update(from_actual)
    return merged


class MusicBrainzPlugin(MusicBrainzAPIMixin, MetadataSourcePlugin):
    @cached_property
    def genres_field(self) -> str:
        return f"{self.config['genres_tag'].as_choice(['genre', 'tag'])}s"

    def __init__(self):
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
                "pseudo_releases": {
                    "scripts": [],
                    "custom_tags_only": False,
                    "multiple_allowed": False,
                    "album_custom_tags": {
                        "album_transl": "album",
                        "album_artist_transl": "artist",
                    },
                    "track_custom_tags": {
                        "title_transl": "title",
                        "artist_transl": "artist",
                    },
                },
            },
        )
        self._apply_pseudo_release_config()
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

    def _apply_pseudo_release_config(self):
        self._scripts = self.config["pseudo_releases"]["scripts"].as_str_seq()
        self._log.debug("Desired pseudo-release scripts: {0}", self._scripts)

        album_custom_tags = (
            self.config["pseudo_releases"]["album_custom_tags"].get().keys()
        )
        track_custom_tags = (
            self.config["pseudo_releases"]["track_custom_tags"].get().keys()
        )
        self._log.debug(
            "Custom tags for albums and tracks: {0} + {1}",
            album_custom_tags,
            track_custom_tags,
        )
        for custom_tag in album_custom_tags | track_custom_tags:
            if not isinstance(custom_tag, str):
                continue

            media_field = mediafile.MediaField(
                mediafile.MP3DescStorageStyle(custom_tag),
                mediafile.MP4StorageStyle(
                    f"----:com.apple.iTunes:{custom_tag}"
                ),
                mediafile.StorageStyle(custom_tag),
                mediafile.ASFStorageStyle(custom_tag),
            )
            try:
                self.add_media_field(custom_tag, media_field)
            except ValueError:
                # ignore errors due to duplicates
                pass

        self.register_listener(
            "album_info_received", self._determine_pseudo_album_info_ref
        )
        self.register_listener("album_matched", self._adjust_final_album_match)

    def _determine_pseudo_album_info_ref(
        self,
        items: Iterable[Item],
        album_info: AlbumInfo,
    ):
        if isinstance(album_info, PseudoAlbumInfo):
            for item in items:
                # particularly relevant for reimport but could also happen during import
                if "mb_albumid" in item:
                    del item["mb_albumid"]
                if "mb_trackid" in item:
                    del item["mb_trackid"]

            self._log.debug(
                "Using {0} release for distance calculations for album {1}",
                album_info.determine_best_ref(list(items)),
                album_info.album_id,
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

        if recording.get("artist-relations"):
            info.remixer = _get_related_artist_names(
                recording["artist-relations"], relation_type="remixer"
            )

        if recording.get("length"):
            info.length = int(recording["length"]) / 1000.0

        info.trackdisambig = recording.get("disambiguation")

        if recording.get("isrcs"):
            info.isrc = ";".join(recording["isrcs"])

        lyricist = []
        composer = []
        composer_sort = []
        for work_relation in recording.get("work-relations", ()):
            if work_relation["type"] != "performance":
                continue
            info.work = work_relation["work"]["title"]
            info.mb_workid = work_relation["work"]["id"]
            if "disambiguation" in work_relation["work"]:
                info.work_disambig = work_relation["work"]["disambiguation"]

            for artist_relation in work_relation["work"].get(
                "artist-relations", ()
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
        for artist_relation in recording.get("artist-relations", ()):
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

    def album_info(self, release: JSONDict) -> AlbumInfo:
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

        ntracks = sum(len(m.get("tracks", [])) for m in release["media"])

        # The MusicBrainz API omits 'relations'
        # when the release has more than 500 tracks. So we use browse_recordings
        # on chunks of tracks to recover the same information in this case.
        if ntracks > BROWSE_MAXTRACKS:
            self._log.debug("Album {} has too many tracks", release["id"])
            recording_list = []
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
                "data-tracks" in medium
                and not config["match"]["ignore_data_tracks"]
            ):
                all_tracks += medium["data-tracks"]
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
        info = AlbumInfo(
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

        if reltype := release["release-group"].get("primary-type"):
            info.albumtype = reltype.lower()

        # Set the new-style "primary" and "secondary" release types.
        albumtypes = []
        if "primary-type" in release["release-group"]:
            rel_primarytype = release["release-group"]["primary-type"]
            if rel_primarytype:
                albumtypes.append(rel_primarytype.lower())
        if "secondary-types" in release["release-group"]:
            if release["release-group"]["secondary-types"]:
                for sec_type in release["release-group"]["secondary-types"]:
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
        if release.get("label-info"):
            label_info = release["label-info"][0]
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
        if release["media"]:
            # If all media are the same, use that medium name
            if len({m.get("format") for m in release["media"]}) == 1:
                info.media = release["media"][0].get("format")
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
            if genres:
                info.genres = [
                    genre
                    for genre, _count in sorted(
                        genres.items(), key=lambda g: -g[1]
                    )
                ]

        # We might find links to external sources (Discogs, Bandcamp, ...)
        external_ids = self.config["external_ids"].get()
        wanted_sources = {
            site for site, wanted in external_ids.items() if wanted
        }
        if wanted_sources and (url_rels := release.get("url-relations")):
            urls = {}

            for source, url in product(wanted_sources, url_rels):
                if f"{source}.com" in (target := url["url"]["resource"]):
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
    ) -> Iterable[AlbumInfo]:
        criteria = self.get_album_criteria(items, artist, album, va_likely)
        release_ids = (r["id"] for r in self._search_api("release", criteria))

        for id_ in release_ids:
            with suppress(HTTPNotFoundError):
                album_info = self.album_for_id(id_)
                # always yield pseudo first to give it priority
                if isinstance(album_info, MultiPseudoAlbumInfo):
                    yield from album_info.unwrap()
                    yield album_info
                elif isinstance(album_info, PseudoAlbumInfo):
                    self._determine_pseudo_album_info_ref(items, album_info)
                    yield album_info
                    yield album_info.get_official_release()
                elif isinstance(album_info, AlbumInfo):
                    yield album_info

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterable[beets.autotag.hooks.TrackInfo]:
        criteria = {"artist": artist, "recording": title, "alias": title}

        yield from filter(
            None, map(self.track_info, self._search_api("recording", criteria))
        )

    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        """Fetches an album by its MusicBrainz ID and returns an AlbumInfo
        object or None if the album is not found.
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

        release = self.album_info(res)

        if res.get("status") == _STATUS_PSEUDO:
            return self._handle_main_pseudo_release(res, release)
        elif pseudo_release_ids := self._intercept_mb_release(res):
            return self._handle_intercepted_pseudo_releases(
                release, pseudo_release_ids
            )
        else:
            return release

    def _handle_main_pseudo_release(
        self,
        pseudo_release: dict[str, Any],
        pseudo_album_info: AlbumInfo,
    ) -> AlbumInfo:
        actual_res = None
        for rel in pseudo_release.get("release-relations", []):
            if (
                rel["type"] == "transl-tracklisting"
                and rel["direction"] == "backward"
            ):
                actual_res = self.mb_api.get_release(rel["release"]["id"])
                if actual_res:
                    break

        if actual_res is None:
            return pseudo_album_info

        actual_release = self.album_info(actual_res)
        merged_release = _merge_pseudo_and_actual_album(
            pseudo_album_info, actual_release
        )

        if self._has_desired_script(pseudo_release):
            return PseudoAlbumInfo(
                pseudo_release=merged_release,
                official_release=actual_release,
            )
        else:
            return merged_release

    def _handle_intercepted_pseudo_releases(
        self,
        release: AlbumInfo,
        pseudo_release_ids: list[str],
    ) -> AlbumInfo:
        languages = list(config["import"]["languages"].as_str_seq())
        pseudo_config = self.config["pseudo_releases"]
        custom_tags_only = pseudo_config["custom_tags_only"].get(bool)

        if len(pseudo_release_ids) == 1 or len(languages) == 0:
            # only 1 pseudo-release or no language preference specified
            album_info = self.mb_api.get_release(pseudo_release_ids[0])
            return self._resolve_pseudo_album_info(
                release, custom_tags_only, languages, album_info
            )

        pseudo_releases = [
            self.mb_api.get_release(i) for i in pseudo_release_ids
        ]

        # sort according to the desired languages specified in the config
        def sort_fun(rel: JSONDict) -> int:
            lang = rel.get("text-representation", {}).get("language", "")
            # noinspection PyBroadException
            try:
                return languages.index(lang[0:2])
            except Exception:
                return len(languages)

        pseudo_releases.sort(key=sort_fun)
        multiple_allowed = pseudo_config["multiple_allowed"].get(bool)
        if custom_tags_only or not multiple_allowed:
            return self._resolve_pseudo_album_info(
                release,
                custom_tags_only,
                languages,
                pseudo_releases[0],
            )

        pseudo_album_infos = [
            self._resolve_pseudo_album_info(
                release, custom_tags_only, languages, i
            )
            for i in pseudo_releases
        ]
        return MultiPseudoAlbumInfo(
            *pseudo_album_infos, official_release=release
        )

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

    def _intercept_mb_release(self, data: JSONDict) -> list[str]:
        album_id = data["id"] if "id" in data else None
        if self._has_desired_script(data) or not isinstance(album_id, str):
            return []

        ans = [
            self._extract_id(pr_id)
            for rel in data.get("release-relations", [])
            if (pr_id := self._wanted_pseudo_release_id(album_id, rel))
            is not None
        ]

        return list(filter(None, ans))

    def _has_desired_script(self, release: JSONDict) -> bool:
        if len(self._scripts) == 0:
            return False
        elif script := release.get("text-representation", {}).get("script"):
            return script in self._scripts
        else:
            return False

    def _wanted_pseudo_release_id(
        self,
        album_id: str,
        relation: JSONDict,
    ) -> str | None:
        if (
            len(self._scripts) == 0
            or relation.get("type", "") != "transl-tracklisting"
            or relation.get("direction", "") != "forward"
            or "release" not in relation
        ):
            return None

        release = relation["release"]
        if "id" in release and self._has_desired_script(release):
            self._log.debug(
                "Adding pseudo-release {0} for main release {1}",
                release["id"],
                album_id,
            )
            return release["id"]
        else:
            return None

    def _resolve_pseudo_album_info(
        self,
        official_release: AlbumInfo,
        custom_tags_only: bool,
        languages: list[str],
        raw_pseudo_release: JSONDict,
    ) -> AlbumInfo:
        pseudo_release = self.album_info(raw_pseudo_release)
        if custom_tags_only:
            self._replace_artist_with_alias(
                languages, raw_pseudo_release, pseudo_release
            )
            self._add_custom_tags(official_release, pseudo_release)
            return official_release
        else:
            return PseudoAlbumInfo(
                pseudo_release=_merge_pseudo_and_actual_album(
                    pseudo_release, official_release
                ),
                official_release=official_release,
            )

    def _replace_artist_with_alias(
        self,
        languages: list[str],
        raw_pseudo_release: JSONDict,
        pseudo_release: AlbumInfo,
    ):
        """Use the pseudo-release's language to search for artist
        alias if the user hasn't configured import languages."""

        if languages:
            return

        lang = raw_pseudo_release.get("text-representation", {}).get("language")
        artist_credits = raw_pseudo_release.get("release-group", {}).get(
            "artist-credit", []
        )
        aliases = [
            artist_credit.get("artist", {}).get("aliases", [])
            for artist_credit in artist_credits
        ]

        if lang and len(lang) >= 2 and len(aliases) > 0:
            locale = lang[0:2]
            aliases_flattened = list(chain.from_iterable(aliases))
            self._log.debug(
                "Using locale '{0}' to search aliases {1}",
                locale,
                aliases_flattened,
            )
            if alias_dict := _preferred_alias(aliases_flattened, [locale]):
                if alias := alias_dict.get("name"):
                    self._log.debug("Got alias '{0}'", alias)
                    pseudo_release.artist = alias
                    for track in pseudo_release.tracks:
                        track.artist = alias

    def _add_custom_tags(
        self,
        official_release: AlbumInfo,
        pseudo_release: AlbumInfo,
    ):
        for tag_key, pseudo_key in (
            self.config["pseudo_releases"]["album_custom_tags"].get().items()
        ):
            official_release[tag_key] = pseudo_release[pseudo_key]

        track_custom_tags = (
            self.config["pseudo_releases"]["track_custom_tags"].get().items()
        )
        for track, pseudo_track in zip(
            official_release.tracks, pseudo_release.tracks
        ):
            for tag_key, pseudo_key in track_custom_tags:
                track[tag_key] = pseudo_track[pseudo_key]

    def _adjust_final_album_match(self, match: AlbumMatch):
        album_info = match.info
        if isinstance(album_info, PseudoAlbumInfo):
            self._log.debug(
                "Switching {0} to pseudo-release source for final proposal",
                album_info.album_id,
            )
            album_info.use_pseudo_as_ref()
            mapping = match.mapping
            new_mappings, _, _ = assign_items(
                list(mapping.keys()), album_info.tracks
            )
            mapping.update(new_mappings)


class PseudoAlbumInfo(AlbumInfo):
    """This is a not-so-ugly hack.

    We want the pseudo-release to result in a distance that is lower or equal to that of
    the official release, otherwise it won't qualify as a good candidate. However, if
    the input is in a script that's different from the pseudo-release (and we want to
    translate/transliterate it in the library), it will receive unwanted penalties.

    This class is essentially a view of the ``AlbumInfo`` of both official and
    pseudo-releases, where it's possible to change the details that are exposed to other
    parts of the auto-tagger, enabling a "fair" distance calculation based on the
    current input's script but still preferring the translation/transliteration in the
    final proposal.
    """

    def __init__(
        self,
        pseudo_release: AlbumInfo,
        official_release: AlbumInfo,
        **kwargs,
    ):
        super().__init__(pseudo_release.tracks, **kwargs)
        self.__dict__["_pseudo_source"] = False
        self.__dict__["_official_release"] = official_release
        for k, v in pseudo_release.items():
            if k not in kwargs:
                self[k] = v

    def get_official_release(self) -> AlbumInfo:
        return self.__dict__["_official_release"]

    def determine_best_ref(self, items: Sequence[Item]) -> str:
        self.use_pseudo_as_ref()
        pseudo_dist = self._compute_distance(items)

        self.use_official_as_ref()
        official_dist = self._compute_distance(items)

        if official_dist < pseudo_dist:
            self.use_official_as_ref()
            return "official"
        else:
            self.use_pseudo_as_ref()
            return "pseudo"

    def _compute_distance(self, items: Sequence[Item]) -> Distance:
        mapping, _, _ = assign_items(items, self.tracks)
        return distance(items, self, mapping)

    def use_pseudo_as_ref(self):
        self.__dict__["_pseudo_source"] = True

    def use_official_as_ref(self):
        self.__dict__["_pseudo_source"] = False

    def __getattr__(self, attr: str) -> Any:
        # ensure we don't duplicate an official release's id, always return pseudo's
        if self.__dict__["_pseudo_source"] or attr == "album_id":
            return super().__getattr__(attr)
        else:
            return self.__dict__["_official_release"].__getattr__(attr)

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)

        memo[id(self)] = result
        result.__dict__.update(self.__dict__)
        for k, v in self.items():
            result[k] = deepcopy(v, memo)

        return result


class MultiPseudoAlbumInfo(AlbumInfo):
    """For releases that have multiple pseudo-releases"""

    def __init__(
        self,
        *args,
        official_release: AlbumInfo,
        **kwargs,
    ):
        super().__init__(official_release.tracks, **kwargs)
        self.__dict__["_pseudo_album_infos"] = [
            arg for arg in args if isinstance(arg, PseudoAlbumInfo)
        ]
        for k, v in official_release.items():
            if k not in kwargs:
                self[k] = v

    def unwrap(self) -> list[PseudoAlbumInfo]:
        return self.__dict__["_pseudo_album_infos"]

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)

        memo[id(self)] = result
        result.__dict__.update(self.__dict__)
        for k, v in self.items():
            result[k] = deepcopy(v, memo)

        return result
